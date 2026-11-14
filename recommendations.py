"""Evaluation engine of the recommendation system (calculations_extended.md, "Recommendation system").

The engine takes the astronaut's inputs, evaluates every rule of recommendation_rules.RULES,
applies the rule combinations, derives a status per body system and an overall status, and
builds a deduplicated, ordered list of recommendations plus a "measure this" list.

All thresholds live in recommendation_rules.py and are informational only: confirm them with
the flight surgeon / medical team. The combinations (sleep + stress, return-phase orthostatic),
the 3+ WATCH escalation and the multi-system review flag are [design] choices, not medical rules.

Everything here is a pure function over immutable data; the input mapping is never mutated.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from Caracteristici import CHARACTERISTIC_DEFINITIONS, Characteristic, is_within_limits
from recommendation_rules import (
    ESCALATION_WATCH_COUNT,
    MULTI_SYSTEM_ACTION_COUNT,
    RESTING_HR_HIGH,
    RULES,
)
from recommendation_types import (
    SYSTEM_ORDER,
    BodySystem,
    ExtraInput,
    InputKey,
    InputValue,
    MissionPhase,
    Rule,
    RuleContext,
    Status,
    make_context,
)

OUT_OF_RANGE_SUFFIX = " (out of range)"

# Characteristics that rules read only to adjust a threshold or a ratio (age for the sleep
# recommendation, height for the waist-to-height ratio). Their own table status is OK when
# present and valid, instead of inheriting the status of the rule they modify.
CONTEXT_ONLY_CHARACTERISTICS: frozenset[Characteristic] = frozenset(
    {Characteristic.AGE, Characteristic.HEIGHT}
)
SLEEP_RULE_IDS: tuple[str, ...] = ("SL-1", "SL-2")
STRESS_RULE_ID = "PS-2"
LOW_BP_RULE_ID = "CV-4"
ORTHOSTATIC_RULE_ID = "CV-6"
SLEEP_STRESS_NOTE = "raised one level: sleep deficit + high stress"
RETURN_ORTHOSTATIC_NOTE = "CV-4 low BP + CV-5 high resting HR in return phase"

_LIMITS_BY_CHARACTERISTIC = {
    definition.characteristic: definition for definition in CHARACTERISTIC_DEFINITIONS
}
_CORE_CHARACTERISTICS: tuple[Characteristic, ...] = tuple(_LIMITS_BY_CHARACTERISTIC)
_KEY_ORDER: tuple[InputKey, ...] = (*_CORE_CHARACTERISTICS, *ExtraInput)
_KEY_INDEX = {key: index for index, key in enumerate(_KEY_ORDER)}
_SYSTEM_INDEX = {system: index for index, system in enumerate(SYSTEM_ORDER)}


@dataclass(frozen=True)
class RuleResult:
    rule: Rule
    status: Status
    missing: tuple[InputKey, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class SystemStatus:
    system: BodySystem
    status: Status
    rule_ids: tuple[str, ...]
    escalated: bool = False


@dataclass(frozen=True)
class Recommendation:
    action: str
    status: Status
    rule_ids: tuple[str, ...]
    systems: tuple[BodySystem, ...]
    sources: tuple[str, ...]
    phase_relevant: bool


@dataclass(frozen=True)
class MissingInput:
    key: InputKey
    label: str
    rule_ids: tuple[str, ...]


@dataclass(frozen=True)
class Assessment:
    phase: MissionPhase
    overall: Status
    multi_system_review: bool
    systems: tuple[SystemStatus, ...]
    results: tuple[RuleResult, ...]
    recommendations: tuple[Recommendation, ...]
    measure_this: tuple[MissingInput, ...]
    invalid_inputs: tuple[InputKey, ...]
    provided: frozenset[InputKey]

    @property
    def is_complete(self) -> bool:
        """True when nothing is left to measure."""
        return not self.measure_this


def _is_valid_core_value(characteristic: Characteristic, value: InputValue) -> bool:
    """A core value must be a real number (not bool, not NaN) inside its definition limits."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if math.isnan(value):
        return False
    return is_within_limits(_LIMITS_BY_CHARACTERISTIC[characteristic], value)


def validate_inputs(
    values: Mapping[InputKey, InputValue],
) -> tuple[dict[InputKey, InputValue], tuple[InputKey, ...]]:
    """Return (clean copy, invalid core keys). None entries are dropped; extras pass through."""
    clean: dict[InputKey, InputValue] = {}
    invalid: list[InputKey] = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(key, Characteristic) and not _is_valid_core_value(key, value):
            invalid.append(key)
            continue
        clean[key] = value
    return clean, tuple(invalid)


def evaluate_rule(rule: Rule, ctx: RuleContext) -> RuleResult:
    """Run one assessor; data errors become UNKNOWN with a note. Missing inputs are listed."""
    note = ""
    try:
        status = rule.assess(ctx)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as error:
        status = Status.UNKNOWN
        note = f"data error: {error}"
    missing: tuple[InputKey, ...] = ()
    if status is Status.UNKNOWN:
        missing = tuple(key for key in rule.inputs if key not in ctx.values)
    return RuleResult(rule=rule, status=status, missing=missing, note=note)


def evaluate_rules(
    ctx: RuleContext, rules: tuple[Rule, ...] = RULES
) -> tuple[RuleResult, ...]:
    """Evaluate every rule in order."""
    return tuple(evaluate_rule(rule, ctx) for rule in rules)


def _raise_one_level(status: Status) -> Status:
    return Status(min(int(status) + 1, int(Status.URGENT)))


def _combine_sleep_and_stress(
    results: tuple[RuleResult, ...],
) -> tuple[RuleResult, ...]:
    """Sleep deficit (SL-1/SL-2) + high stress (PS-2): raise each firing rule one level."""
    stress = next((r for r in results if r.rule.id == STRESS_RULE_ID), None)
    sleep_firing = [
        r for r in results if r.rule.id in SLEEP_RULE_IDS and r.status >= Status.WATCH
    ]
    if stress is None or stress.status < Status.ACTION or not sleep_firing:
        return results
    raised_ids = {r.rule.id for r in sleep_firing} | {STRESS_RULE_ID}
    return tuple(
        replace(r, status=_raise_one_level(r.status), note=SLEEP_STRESS_NOTE)
        if r.rule.id in raised_ids
        else r
        for r in results
    )


def _combine_return_orthostatic(
    results: tuple[RuleResult, ...], ctx: RuleContext
) -> tuple[RuleResult, ...]:
    """Return phase: low BP (CV-4) with high resting HR makes CV-6 at least ACTION."""
    if ctx.phase is not MissionPhase.RETURN:
        return results
    low_bp = next((r for r in results if r.rule.id == LOW_BP_RULE_ID), None)
    heart_rate = ctx.get(Characteristic.AVERAGE_HEART_RATE)
    if low_bp is None or low_bp.status < Status.WATCH:
        return results
    if isinstance(heart_rate, bool) or not isinstance(heart_rate, (int, float)):
        return results
    if heart_rate <= RESTING_HR_HIGH:
        return results
    return tuple(
        replace(r, status=Status.ACTION, missing=(), note=RETURN_ORTHOSTATIC_NOTE)
        if r.rule.id == ORTHOSTATIC_RULE_ID and r.status < Status.ACTION
        else r
        for r in results
    )


def apply_combinations(
    results: tuple[RuleResult, ...], ctx: RuleContext
) -> tuple[RuleResult, ...]:
    """Apply the [design] combinations; never lowers a status. Returns new results."""
    combined = _combine_sleep_and_stress(results)
    return _combine_return_orthostatic(combined, ctx)


def _system_status(system: BodySystem, results: tuple[RuleResult, ...]) -> SystemStatus:
    relevant = [r for r in results if system in r.rule.protects]
    known = [r.status for r in relevant if r.status is not Status.UNKNOWN]
    status = max(known, default=Status.UNKNOWN)
    escalated = False
    if status is Status.WATCH and known.count(Status.WATCH) >= ESCALATION_WATCH_COUNT:
        status, escalated = Status.ACTION, True
    if status is Status.OK and any(
        r.status is Status.UNKNOWN
        and any(isinstance(key, Characteristic) for key in r.missing)
        for r in relevant
    ):
        status = Status.UNKNOWN
    fired = tuple(r.rule.id for r in relevant if r.status >= Status.WATCH)
    return SystemStatus(system=system, status=status, rule_ids=fired, escalated=escalated)


def system_statuses(results: tuple[RuleResult, ...]) -> tuple[SystemStatus, ...]:
    """One SystemStatus per body system, in SYSTEM_ORDER."""
    return tuple(_system_status(system, results) for system in SYSTEM_ORDER)


def overall_status(systems: tuple[SystemStatus, ...], core_missing: bool) -> Status:
    """Highest known system status; OK is never reported when core data is missing."""
    top = max(
        (s.status for s in systems if s.status is not Status.UNKNOWN),
        default=Status.UNKNOWN,
    )
    if top is Status.OK and core_missing:
        return Status.UNKNOWN
    return top


def needs_multi_system_review(systems: tuple[SystemStatus, ...]) -> bool:
    """True when ACTION (or worse) is present on enough systems."""
    return sum(1 for s in systems if s.status >= Status.ACTION) >= MULTI_SYSTEM_ACTION_COUNT


def _recommendation_sort_key(
    entry: tuple[Recommendation, int],
) -> tuple[int, bool, int, int]:
    recommendation, first_index = entry
    best_system = min(_SYSTEM_INDEX[s] for s in recommendation.systems)
    return (
        -int(recommendation.status),
        not recommendation.phase_relevant,
        best_system,
        first_index,
    )


def _merge_action(
    action: str,
    members: list[tuple[int, RuleResult]],
    phase: MissionPhase,
) -> tuple[Recommendation, int]:
    rules = [result.rule for _, result in members]
    systems = {system for rule in rules for system in rule.protects}
    sources = tuple(dict.fromkeys(rule.source for rule in rules))
    recommendation = Recommendation(
        action=action,
        status=max(result.status for _, result in members),
        rule_ids=tuple(rule.id for rule in rules),
        systems=tuple(s for s in SYSTEM_ORDER if s in systems),
        sources=sources,
        phase_relevant=phase is not MissionPhase.UNKNOWN
        and any(phase in rule.phases for rule in rules),
    )
    return recommendation, members[0][0]


def build_recommendations(
    results: tuple[RuleResult, ...], phase: MissionPhase
) -> tuple[Recommendation, ...]:
    """Merge identical actions of firing rules and sort by the priority rules."""
    grouped: dict[str, list[tuple[int, RuleResult]]] = {}
    for index, result in enumerate(results):
        if result.status < Status.WATCH:
            continue
        for action in result.rule.actions:
            grouped.setdefault(action, []).append((index, result))
    merged = [_merge_action(action, members, phase) for action, members in grouped.items()]
    return tuple(rec for rec, _ in sorted(merged, key=_recommendation_sort_key))


def _label_for(key: InputKey, invalid: frozenset[InputKey]) -> str:
    return key.value + (OUT_OF_RANGE_SUFFIX if key in invalid else "")


def collect_missing(results: tuple[RuleResult, ...]) -> tuple[MissingInput, ...]:
    """Missing inputs of UNKNOWN results, merged by key (core first, then extras)."""
    rule_ids_by_key: dict[InputKey, list[str]] = {}
    for result in results:
        if result.status is not Status.UNKNOWN:
            continue
        for key in result.missing:
            rule_ids_by_key.setdefault(key, []).append(result.rule.id)
    ordered = sorted(rule_ids_by_key, key=lambda key: _KEY_INDEX[key])
    return tuple(
        MissingInput(key=key, label=key.value, rule_ids=tuple(rule_ids_by_key[key]))
        for key in ordered
    )


def _measure_this(
    results: tuple[RuleResult, ...],
    provided: frozenset[InputKey],
    invalid: tuple[InputKey, ...],
) -> tuple[MissingInput, ...]:
    """collect_missing plus core characteristics that are absent/invalid but read by no UNKNOWN rule."""
    collected = {item.key: item for item in collect_missing(results)}
    invalid_set = frozenset(invalid)
    for key in _CORE_CHARACTERISTICS:
        if key not in provided and key not in collected:
            collected[key] = MissingInput(key=key, label=key.value, rule_ids=())
    ordered = sorted(collected.values(), key=lambda item: _KEY_INDEX[item.key])
    return tuple(
        replace(item, label=_label_for(item.key, invalid_set)) for item in ordered
    )


def characteristic_status(assessment: Assessment, characteristic: Characteristic) -> Status:
    """Status of the rules that read this characteristic.

    UNKNOWN if the value is missing or invalid, or if every rule reading it is UNKNOWN
    (undecidable never counts as OK). OK when no rule reads it or none fired.
    """
    if characteristic not in assessment.provided:
        return Status.UNKNOWN
    if characteristic in CONTEXT_ONLY_CHARACTERISTICS:
        return Status.OK
    statuses = [r.status for r in assessment.results if characteristic in r.rule.inputs]
    known = [status for status in statuses if status is not Status.UNKNOWN]
    if statuses and not known:
        return Status.UNKNOWN
    return max(known, default=Status.OK)


def assess(
    values: Mapping[InputKey, InputValue],
    phase: MissionPhase = MissionPhase.UNKNOWN,
    rules: tuple[Rule, ...] = RULES,
) -> Assessment:
    """Full pipeline: validate, evaluate, combine, summarise. Never mutates `values`."""
    clean, invalid = validate_inputs(values)
    ctx = make_context(clean, phase)
    results = apply_combinations(evaluate_rules(ctx, rules), ctx)
    systems = system_statuses(results)
    provided = frozenset(clean)
    core_missing = any(key not in provided for key in _CORE_CHARACTERISTICS)
    return Assessment(
        phase=phase,
        overall=overall_status(systems, core_missing),
        multi_system_review=needs_multi_system_review(systems),
        systems=systems,
        results=results,
        recommendations=build_recommendations(results, phase),
        measure_this=_measure_this(results, provided, invalid),
        invalid_inputs=invalid,
        provided=provided,
    )
