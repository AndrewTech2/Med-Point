"""Terminal view (demo) of the Med-Point recommendation system.

Renders, per astronaut: overall status, the 14 stored characteristics, the status
of the 10 body systems, ordered recommendations and the "measure this" list.
Data come from fictional demo astronauts (--demo) or from the astronauti database,
which is opened strictly read-only.

DISCLAIMER: all thresholds are informational. Confirm them with the flight
surgeon / medical team before acting on anything shown here.
"""

import argparse
import contextlib
import os
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import TextIO

from calculations import connect_read_only, load_astronauts, printable
from Caracteristici import CHARACTERISTIC_DEFINITIONS, DB_PATH
from dashboard_demo_data import DEMO_ASTRONAUTS, AstronautRecord
from recommendation_types import MissionPhase, Status
from recommendations import Assessment, assess, characteristic_status

DISCLAIMER = (
    "DISCLAIMER: thresholds are informational; confirm with the flight surgeon / medical team."
)
MISSING_VALUE = "-"
RULE_WIDTH = 78
ANSI_RESET = "\033[0m"
STATUS_COLORS: dict[Status, str] = {
    Status.URGENT: "\033[1;31m",
    Status.ACTION: "\033[35m",
    Status.WATCH: "\033[33m",
    Status.OK: "\033[32m",
    Status.UNKNOWN: "\033[2;37m",
}


def colorize(text: str, status: Status, use_color: bool) -> str:
    """Wrap `text` in the ANSI colour of `status` when colours are enabled."""
    if not use_color:
        return text
    return f"{STATUS_COLORS[status]}{text}{ANSI_RESET}"


def should_use_color(no_color: bool, stream: TextIO) -> bool:
    """False with --no-color, with the NO_COLOR variable set, or when stream is not a TTY."""
    if no_color or os.environ.get("NO_COLOR"):
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _status_cell(status: Status, width: int, use_color: bool) -> str:
    return colorize(status.name.ljust(width), status, use_color)


def _format_value(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return f"{value:g}"


def _table(headers: Sequence[str], widths: Sequence[int], rows: Sequence[Sequence[str]]) -> str:
    """Plain-ASCII table; cells are already padded or deliberately free-form (last column)."""
    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    head = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([border, head, border, *body, border])


def render_characteristics_table(
    record: AstronautRecord, assessment: Assessment, use_color: bool
) -> str:
    """The 14 stored characteristics with value, unit and status."""
    widths = (34, 10, 8, 8)
    rows: list[list[str]] = []
    for definition in CHARACTERISTIC_DEFINITIONS:
        key = definition.characteristic
        value = record.values.get(key)
        text = MISSING_VALUE if value is None else _format_value(value)
        if key in assessment.invalid_inputs:
            text = f"{text}!"
        status = characteristic_status(assessment, key)
        rows.append([
            key.value.ljust(widths[0]),
            text.rjust(widths[1]),
            definition.unit.ljust(widths[2]),
            _status_cell(status, widths[3], use_color),
        ])
    table = _table(("Characteristic", "Value", "Unit", "Status"), widths, rows)
    if assessment.invalid_inputs:
        table += "\n(!) value outside the allowed range: treated as missing"
    return table


def render_systems(assessment: Assessment, use_color: bool) -> str:
    """Status of all body systems, with escalation marker and contributing rule ids."""
    widths = (24, 8, 9, 30)
    rows = [
        [
            item.system.value.ljust(widths[0]),
            _status_cell(item.status, widths[1], use_color),
            ("escalated" if item.escalated else "").ljust(widths[2]),
            ", ".join(item.rule_ids).ljust(widths[3]),
        ]
        for item in assessment.systems
    ]
    return _table(("Body system", "Status", "Note", "Rules"), widths, rows)


def render_recommendations(assessment: Assessment, use_color: bool) -> str:
    """Ordered recommendations, most severe first."""
    if not assessment.recommendations:
        return "  No recommendations."
    lines: list[str] = []
    for index, rec in enumerate(assessment.recommendations, start=1):
        label = colorize(f"[{rec.status.name}]", rec.status, use_color)
        phase = " (phase-relevant)" if rec.phase_relevant else ""
        lines.append(f"  {index}. {label} {rec.action}{phase}")
        lines.append(f"       rules: {', '.join(rec.rule_ids)} | sources: {' / '.join(rec.sources)}")
        lines.append(f"       systems: {', '.join(s.value for s in rec.systems)}")
    return "\n".join(lines)


def render_measure_this(assessment: Assessment) -> str:
    """Inputs that would let more rules be decided."""
    if not assessment.measure_this:
        return "  Nothing to measure: data complete."
    return "\n".join(
        f"  - {item.label} (rules: {', '.join(item.rule_ids)})"
        for item in assessment.measure_this
    )


def _header(record: AstronautRecord, assessment: Assessment, use_color: bool) -> str:
    overall = colorize(assessment.overall.name, assessment.overall, use_color)
    review = "YES" if assessment.multi_system_review else "no"
    count = len(assessment.measure_this)
    data = "data complete" if assessment.is_complete else f"{count} inputs to measure"
    title = printable(f"{record.last_name} {record.first_name}")
    return "\n".join([
        "=" * RULE_WIDTH,
        f"{title} | phase: {assessment.phase.value} | overall: {overall}",
        f"Multi-system review: {review} | {data}",
        f"({printable(record.note)})" if record.note else "",
        "=" * RULE_WIDTH,
    ]).replace("\n\n", "\n")


def render_astronaut(record: AstronautRecord, assessment: Assessment, use_color: bool) -> str:
    """Full text block for one astronaut."""
    return "\n".join([
        _header(record, assessment, use_color),
        render_characteristics_table(record, assessment, use_color),
        "",
        "Body systems",
        render_systems(assessment, use_color),
        "",
        "Recommendations",
        render_recommendations(assessment, use_color),
        "",
        "Measure this",
        render_measure_this(assessment),
        "",
    ])


def _resolve_phase(record: AstronautRecord, override: MissionPhase | None) -> MissionPhase:
    if override is not None:
        return override
    return record.phase or MissionPhase.UNKNOWN


def render_report(
    records: Sequence[AstronautRecord], phase_override: MissionPhase | None, use_color: bool
) -> str:
    """Disclaimer followed by one block per astronaut."""
    blocks = [DISCLAIMER, ""]
    for record in records:
        phase = _resolve_phase(record, phase_override)
        blocks.append(render_astronaut(record, assess(record.values, phase), use_color))
    return "\n".join(blocks)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _load_legacy_names(conn: sqlite3.Connection) -> tuple[AstronautRecord, ...]:
    """Old Romanian 'astronauti' table: names only, so every characteristic is None (UNKNOWN)."""
    empty = MappingProxyType({d.characteristic: None for d in CHARACTERISTIC_DEFINITIONS})
    rows = conn.execute("SELECT nume, prenume FROM astronauti ORDER BY id").fetchall()
    return tuple(AstronautRecord(last, first, empty) for last, first in rows)


def load_db_astronauts(db_path: Path) -> tuple[AstronautRecord, ...]:
    """Read astronauts from the database, strictly read-only (never creates or writes)."""
    with contextlib.closing(connect_read_only(db_path)) as conn:
        if not _has_table(conn, "astronauts") and _has_table(conn, "astronauti"):
            return _load_legacy_names(conn)
        stored = load_astronauts(conn)
    return tuple(
        AstronautRecord(last, first, MappingProxyType(dict(values)))
        for (last, first), values in stored.items()
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Terminal view of the Med-Point recommendation system. " + DISCLAIMER
    )
    parser.add_argument("--demo", action="store_true", help="use fictional demo astronauts")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colours")
    parser.add_argument(
        "--phase",
        choices=[phase.value for phase in MissionPhase],
        default=None,
        help="mission phase (default: demo record phase / unknown for the database)",
    )
    parser.add_argument("--astronaut", default=None, help='filter by "Last First"')
    parser.add_argument("--db", type=Path, default=DB_PATH, help="database path")
    return parser.parse_args(argv)


def _select(records: Sequence[AstronautRecord], name: str | None) -> tuple[AstronautRecord, ...]:
    if name is None:
        return tuple(records)
    wanted = " ".join(name.split()).casefold()
    return tuple(r for r in records if f"{r.last_name} {r.first_name}".casefold() == wanted)


def _load_records(args: argparse.Namespace) -> tuple[AstronautRecord, ...] | None:
    """Records for the run, or None after printing an error message."""
    if args.demo:
        return DEMO_ASTRONAUTS
    if not args.db.exists():
        print(f"Database not found: {printable(str(args.db))}. Nothing was created; use --demo for sample data.")
        return None
    try:
        return load_db_astronauts(args.db)
    except sqlite3.Error as error:
        print(f"Database error: {error}")
        return None


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = parse_args(argv)
    records = _load_records(args)
    if records is None:
        return 1
    selected = _select(records, args.astronaut)
    if not selected:
        print(f"No astronaut matched: {args.astronaut!r} (use \"Last First\").")
        return 1
    phase = MissionPhase(args.phase) if args.phase else None
    use_color = should_use_color(args.no_color, sys.stdout)
    print(render_report(selected, phase, use_color))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
