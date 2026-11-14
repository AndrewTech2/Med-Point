"""Write every astronaut's measurement history for the frontend graphs.

Usage: python export_history.py [--db PATH] [--out PATH]
Creates health_history.js next to the page. Run it again after new measurements are saved.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from Caracteristici import CHARACTERISTIC_DEFINITIONS, DB_PATH
from calculations import connect_read_only, printable
from historic import list_history, summarise

DEFAULT_OUT = Path(__file__).with_name("Med-Point-fixed") / "Med-Point Interface" / "health_history.js"


def build_export(conn) -> dict:
    """Per astronaut (database id and name) and characteristic: label, unit, (time, value) points and the summary."""
    astronauts = []
    rows = conn.execute("SELECT id, last_name, first_name FROM astronauts ORDER BY id").fetchall()
    for astronaut_id, last_name, first_name in rows:
        history = list_history(conn, astronaut_id)
        metrics = {}
        for definition in CHARACTERISTIC_DEFINITIONS:
            characteristic = definition.characteristic
            summary = summarise(history, characteristic)
            if summary.count:
                metrics[characteristic.name] = {
                    "label": characteristic.value,
                    "unit": definition.unit,
                    "points": [
                        [when, row[characteristic]]
                        for when, row in history
                        if row[characteristic] is not None
                    ],
                    "summary": summary._asdict(),
                }
        astronauts.append(
            {"id": astronaut_id, "name": printable(f"{last_name} {first_name}"), "metrics": metrics}
        )
    return {"astronauts": astronauts}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export measurement history for the frontend.")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="database file (read-only)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="file to write")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"Database {printable(args.db.name)} not found. Run Caracteristici.py first.")
        return 1
    with closing(connect_read_only(args.db)) as conn:
        data = build_export(conn)
    args.out.write_text(
        f"window.MED_POINT_HISTORY = {json.dumps(data, indent=1)};\n", encoding="utf-8"
    )
    print(f"Wrote {len(data['astronauts'])} astronaut(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
