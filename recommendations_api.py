"""JSON view of the recommendation engine, used by the /api/astronauts/<id>/recommendations route.

Everything here is a pure function: inputs are never mutated and every payload is built fresh.
Only the names and the disclaimer leave this module; thresholds stay in recommendation_rules.py.
"""

import sqlite3
from collections.abc import Mapping
from types import MappingProxyType

from calculations import printable
from Caracteristici import CHARACTERISTIC_COLUMNS, CHARACTERISTIC_DEFINITIONS, Characteristic
from dashboard_terminal import DISCLAIMER
from recommendation_rules import RULES
from recommendation_types import BodySystem, MissionPhase, Rule, Status
from recommendations import (
    CONTEXT_ONLY_CHARACTERISTICS,
    Assessment,
    Recommendation,
    assess,
)

DEMOGRAPHIC_CHARACTERISTICS: tuple[Characteristic, ...] = (
    Characteristic.AGE,
    Characteristic.BODY_WEIGHT,
    Characteristic.HEIGHT,
)
MEASUREMENT_CHARACTERISTICS: tuple[Characteristic, ...] = tuple(
    definition.characteristic
    for definition in CHARACTERISTIC_DEFINITIONS
    if definition.characteristic not in DEMOGRAPHIC_CHARACTERISTICS
)
_DEFINITION_INDEX = {
    definition.characteristic: index
    for index, definition in enumerate(CHARACTERISTIC_DEFINITIONS)
}
_RULES_BY_ID: Mapping[str, Rule] = MappingProxyType({rule.id: rule for rule in RULES})

REGION_SYSTEMS: Mapping[str, tuple[BodySystem, ...]] = MappingProxyType(
    {
        "head": (BodySystem.BRAIN, BodySystem.EYES, BodySystem.SLEEP),
        "torso": (
            BodySystem.HEART_VESSELS,
            BodySystem.BLOOD,
            BodySystem.METABOLISM,
            BodySystem.KIDNEYS_FLUIDS,
            BodySystem.IMMUNE,
        ),
        "arms": (BodySystem.MUSCLES,),
        "legs": (BodySystem.BONES,),
    }
)
STATUS_SCORES: Mapping[Status, int] = MappingProxyType(
    {Status.OK: 100, Status.WATCH: 65, Status.ACTION: 45, Status.URGENT: 15}
)


def load_latest(
    conn: sqlite3.Connection, astronaut_id: int
) -> tuple[str, str | None, dict[Characteristic, float | None]] | None:
    """Return (name, recorded_at of the latest measurement, values); None if the id is unknown."""
    row = conn.execute(_latest_sql(), (astronaut_id,)).fetchone()
    if row is None:
        return None
    last_name, first_name, recorded_at = row[0], row[1], row[5]
    values: dict[Characteristic, float | None] = dict(zip(DEMOGRAPHIC_CHARACTERISTICS, row[2:5]))
    values.update(zip(MEASUREMENT_CHARACTERISTICS, row[6:]))
    return printable(f"{last_name} {first_name}"), recorded_at, values


def _latest_sql() -> str:
    """SQL with only column names taken from CHARACTERISTIC_COLUMNS; the id is a bound parameter."""
    demographic = [f"a.{CHARACTERISTIC_COLUMNS[c]}" for c in DEMOGRAPHIC_CHARACTERISTICS]
    measured = [f"m.{CHARACTERISTIC_COLUMNS[c]}" for c in MEASUREMENT_CHARACTERISTICS]
    columns = ", ".join(["a.last_name", "a.first_name", *demographic, "m.recorded_at", *measured])
    return f"""SELECT {columns}
        FROM astronauts AS a
        LEFT JOIN measurement_history AS m
            ON m.id = (
                SELECT latest.id
                FROM measurement_history AS latest
                WHERE latest.astronaut_id = a.id
                ORDER BY latest.recorded_at DESC, latest.id DESC
                LIMIT 1
            )
        WHERE a.id = ?"""


def region_scores(assessment: Assessment) -> dict[str, int]:
    """Score 0-100 per body region from its worst KNOWN system; regions with no known system are omitted."""
    statuses = {system.system: system.status for system in assessment.systems}
    scores: dict[str, int] = {}
    for region, systems in REGION_SYSTEMS.items():
        known = [statuses[s] for s in systems if statuses.get(s, Status.UNKNOWN) is not Status.UNKNOWN]
        if known:
            scores[region] = STATUS_SCORES[max(known)]
    return scores


def _metric_names(rules: list[Rule]) -> list[str]:
    """Characteristic names read by the rules, minus context-only ones, in definition order."""
    inputs = {
        key
        for rule in rules
        for key in rule.inputs
        if isinstance(key, Characteristic) and key not in CONTEXT_ONLY_CHARACTERISTICS
    }
    return [c.name for c in sorted(inputs, key=lambda c: _DEFINITION_INDEX[c])]


def _body_regions(systems: tuple[BodySystem, ...]) -> list[str]:
    return [
        region
        for region, region_systems in REGION_SYSTEMS.items()
        if any(system in region_systems for system in systems)
    ]


def recommendation_to_dict(recommendation: Recommendation) -> dict:
    rules = [_RULES_BY_ID[rule_id] for rule_id in recommendation.rule_ids]
    return {
        "action": recommendation.action,
        "status": recommendation.status.name,
        "level": int(recommendation.status),
        "rule_ids": list(recommendation.rule_ids),
        "rules": [
            {"id": rule.id, "variable": rule.variable, "condition": rule.condition}
            for rule in rules
        ],
        "systems": [system.value for system in recommendation.systems],
        "metrics": _metric_names(rules),
        "body_regions": _body_regions(recommendation.systems),
        "sources": list(recommendation.sources),
        "phase_relevant": recommendation.phase_relevant,
    }


def _measure_this_list(assessment: Assessment) -> list[dict]:
    return [{"key": item.key.name, "label": item.label} for item in assessment.measure_this]


def build_payload(
    astronaut_id: int,
    name: str,
    recorded_at: str | None,
    values: Mapping,
    phase: MissionPhase = MissionPhase.UNKNOWN,
) -> dict:
    """Run the engine on `values` and return the JSON contract of the recommendations route."""
    assessment = assess(values, phase)
    return {
        "astronaut_id": astronaut_id,
        "name": name,
        "recorded_at": recorded_at,
        "phase": phase.value,
        "overall": assessment.overall.name,
        "overall_level": int(assessment.overall),
        "multi_system_review": assessment.multi_system_review,
        "recommendations": [recommendation_to_dict(r) for r in assessment.recommendations],
        "regions": region_scores(assessment),
        "measure_this": _measure_this_list(assessment),
        "disclaimer": DISCLAIMER,
    }


def payload_for_astronaut(
    conn: sqlite3.Connection,
    astronaut_id: int,
    phase: MissionPhase = MissionPhase.UNKNOWN,
) -> dict | None:
    """Load the latest data of one astronaut and return its payload; None if the id is unknown."""
    loaded = load_latest(conn, astronaut_id)
    if loaded is None:
        return None
    name, recorded_at, values = loaded
    return build_payload(astronaut_id, name, recorded_at, values, phase)
