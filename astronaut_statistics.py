"""Summary (and optional charts) of every astronaut's measurement history.

Usage: python astronaut_statistics.py [--plot] [--db PATH]
The summaries need nothing extra. --plot needs plotly (pip install plotly).
Single-astronaut view: historic.py.
"""

import argparse
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from Caracteristici import CHARACTERISTIC_DEFINITIONS, DB_PATH, Characteristic
from calculations import connect_read_only, printable
from historic import HistoryRow, format_summary, list_history, summarise


def show_chart(title: str, history: Sequence[HistoryRow], characteristic: Characteristic) -> None:
    import plotly.express  # optional dependency, imported only when charts are asked for

    points = [(when, row[characteristic]) for when, row in history if row[characteristic] is not None]
    if points:
        times, values = zip(*points)
        plotly.express.line(x=times, y=values, title=title).show()


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="History summary of every astronaut.")
    parser.add_argument("--plot", action="store_true", help="also open one chart per value")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="database file (read-only)")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"Database {printable(args.db.name)} not found. Run Caracteristici.py first.")
        return 1
    with closing(connect_read_only(args.db)) as conn:
        astronauts = conn.execute(
            "SELECT id, last_name, first_name FROM astronauts ORDER BY id"
        ).fetchall()
        histories = {row[0]: list_history(conn, row[0]) for row in astronauts}

    for astronaut_id, last_name, first_name in astronauts:
        name = printable(f"{last_name} {first_name}")
        history = histories[astronaut_id]
        print(f"\n{name}: {len(history)} measurement(s)")
        for definition in CHARACTERISTIC_DEFINITIONS:
            characteristic = definition.characteristic
            print(" ", format_summary(characteristic, summarise(history, characteristic)))
            if args.plot:
                try:
                    show_chart(f"{name}: {characteristic.value}", history, characteristic)
                except ModuleNotFoundError:
                    print("Charts need plotly: pip install plotly")
                    return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
