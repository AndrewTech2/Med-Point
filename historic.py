"""Per-astronaut measurement history read from measurement_history (read-only).

Usage: python historic.py "Last First" [--characteristic NAME] [--db PATH]
"""

import argparse
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

from Caracteristici import CHARACTERISTIC_DEFINITIONS, DB_PATH, Characteristic, column_name
from calculations import connect_read_only, printable

HistoryRow = tuple[str, dict[Characteristic, float | None]]


class Summary(NamedTuple):
    count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    first: float | None
    last: float | None
    change: float | None


def list_history(conn: sqlite3.Connection, astronaut_id: int) -> list[HistoryRow]:
    """Return (recorded_at, values) for every measurement, oldest first."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(measurement_history)")}
    columns = ", ".join(
        column_name(d.characteristic) if column_name(d.characteristic) in existing else "NULL"
        for d in CHARACTERISTIC_DEFINITIONS
    )  # databases saved before age/weight/height history existed give None for those
    rows = conn.execute(
        f"""SELECT recorded_at, {columns}
        FROM measurement_history
        WHERE astronaut_id = ?
        ORDER BY recorded_at, id""",
        (astronaut_id,),
    ).fetchall()
    return [
        (
            row[0],
            {d.characteristic: row[i + 1] for i, d in enumerate(CHARACTERISTIC_DEFINITIONS)},
        )
        for row in rows
    ]


def summarise(history: Sequence[HistoryRow], characteristic: Characteristic) -> Summary:
    """Min, max, mean, first, last and change of one characteristic, ignoring None."""
    values = [v for _, row in history if (v := row.get(characteristic)) is not None]
    if not values:
        return Summary(0, None, None, None, None, None, None)
    return Summary(
        count=len(values),
        minimum=min(values),
        maximum=max(values),
        mean=sum(values) / len(values),
        first=values[0],
        last=values[-1],
        change=values[-1] - values[0],
    )


def find_astronaut_id(conn: sqlite3.Connection, full_name: str) -> int | None:
    """Look up "Last First" (case-insensitive); names may contain spaces."""
    parts = full_name.split()
    for split_at in range(1, len(parts)):
        row = conn.execute(
            """SELECT id FROM astronauts
            WHERE last_name = ? COLLATE NOCASE AND first_name = ? COLLATE NOCASE""",
            (" ".join(parts[:split_at]), " ".join(parts[split_at:])),
        ).fetchone()
        if row is not None:
            return row[0]
    return None


def parse_characteristic(name: str) -> Characteristic | None:
    return Characteristic.__members__.get(name.strip().upper())


def format_summary(characteristic: Characteristic, summary: Summary) -> str:
    unit = next(d.unit for d in CHARACTERISTIC_DEFINITIONS if d.characteristic is characteristic)
    label = f"{characteristic.value} ({unit})"
    if summary.count == 0:
        return f"{label}: no values recorded"
    return (
        f"{label}: n={summary.count} min={summary.minimum:g} max={summary.maximum:g} "
        f"mean={summary.mean:.2f} first={summary.first:g} last={summary.last:g} "
        f"change={summary.change:+g}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="Show an astronaut's measurement history.")
    parser.add_argument("name", help='astronaut name as "Last First"')
    parser.add_argument(
        "--characteristic",
        help="one characteristic, e.g. BLOOD_GLUCOSE; choices: "
        + ", ".join(Characteristic.__members__),
    )
    parser.add_argument("--db", type=Path, default=DB_PATH, help="database file (read-only)")
    args = parser.parse_args(argv)

    if args.characteristic is None:
        selected = [d.characteristic for d in CHARACTERISTIC_DEFINITIONS]
    elif (characteristic := parse_characteristic(args.characteristic)) is None:
        print(f"Unknown characteristic: {printable(args.characteristic)}")
        return 1
    else:
        selected = [characteristic]

    if not args.db.exists():
        print(f"Database {printable(args.db.name)} not found. Run Caracteristici.py first.")
        return 1
    with closing(connect_read_only(args.db)) as conn:
        astronaut_id = find_astronaut_id(conn, args.name)
        if astronaut_id is None:
            print(f"Astronaut not found: {printable(args.name)}")
            return 1
        history = list_history(conn, astronaut_id)

    print(f"History for {printable(args.name)}: {len(history)} measurement(s)")
    if history:
        print(f"From {history[0][0]} to {history[-1][0]}")
    for characteristic in selected:
        print(format_summary(characteristic, summarise(history, characteristic)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
