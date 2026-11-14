from contextlib import closing
from pathlib import Path

import pandas as pd

from calculations import connect_read_only, printable

DB_FILE = Path(__file__).with_name("astronauts.db")
TABLE_NAME = "astronauts"
MEASUREMENT_TABLE_NAME = "measurement_history"
LAST_NAME_COLUMN = "last_name"
FIRST_NAME_COLUMN = "first_name"
PULSE_COLUMN = "average_pulse"
SYSTOLIC_COLUMN = "systolic_pressure"
BMI_COLUMN = "bmi"
RADIATION_COLUMN = "radiation_levels"
BONE_DENSITY_COLUMN = "bone_density"


def evaluate_pulse(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if value < 50 or value > 115:
        return "Critical"
    if (50 <= value < 60) or (100 < value <= 115):
        return "Warning"
    return "Healthy"


def evaluate_systolic(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if value < 90 or value >= 140:
        return "Critical"
    if 120 < value <= 139:
        return "Warning"
    return "Healthy"


def evaluate_bmi(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if value < 17.0 or value >= 30.0:
        return "Critical"
    if (17.0 <= value < 18.5) or (25.0 < value <= 29.9):
        return "Warning"
    return "Healthy"


def evaluate_radiation(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if value > 100:
        return "Critical"
    if 50 < value <= 100:
        return "Warning"
    return "Healthy"


def evaluate_bone_density(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if value < 0.7 or value > 1.6:
        return "Critical"
    if (0.7 <= value < 0.9) or (1.4 < value <= 1.6):
        return "Warning"
    return "Healthy"


def overall_status(statuses: list[str]) -> str:
    active_statuses = [status for status in statuses if status != "Unknown"]
    if "Critical" in active_statuses:
        return "Critical"
    if "Warning" in active_statuses:
        return "Warning"
    return "Healthy"


def analyze_row(row: dict) -> dict:
    statuses = {
        "Pulse": evaluate_pulse(row.get(PULSE_COLUMN)),
        "Systolic Pressure": evaluate_systolic(row.get(SYSTOLIC_COLUMN)),
        "BMI": evaluate_bmi(row.get(BMI_COLUMN)),
    }

    if RADIATION_COLUMN in row and row.get(RADIATION_COLUMN) is not None:
        statuses["Radiation"] = evaluate_radiation(row.get(RADIATION_COLUMN))
    if BONE_DENSITY_COLUMN in row and row.get(BONE_DENSITY_COLUMN) is not None:
        statuses["Bone Density"] = evaluate_bone_density(row.get(BONE_DENSITY_COLUMN))

    statuses["Overall Status"] = overall_status(list(statuses.values()))
    return statuses


def load_data(db_path: str | Path = DB_FILE, table_name: str = TABLE_NAME) -> pd.DataFrame:
    if table_name != TABLE_NAME:
        raise ValueError(f"Unsupported table: {table_name!r}")
    with closing(connect_read_only(Path(db_path))) as conn:
        return pd.read_sql_query(
            f"""SELECT a.{FIRST_NAME_COLUMN}, a.{LAST_NAME_COLUMN},
                       m.{PULSE_COLUMN}, m.{SYSTOLIC_COLUMN}, m.{BMI_COLUMN},
                       m.{RADIATION_COLUMN}, m.{BONE_DENSITY_COLUMN}
                FROM {table_name} AS a
                LEFT JOIN {MEASUREMENT_TABLE_NAME} AS m
                    ON m.id = (
                        SELECT latest.id
                        FROM {MEASUREMENT_TABLE_NAME} AS latest
                        WHERE latest.astronaut_id = a.id
                        ORDER BY latest.recorded_at DESC, latest.id DESC
                        LIMIT 1
                    )
                ORDER BY a.id""",
            conn,
        )


def main(db_path: str | Path = DB_FILE) -> None:
    df = load_data(db_path)

    print("=== ASTRONAUT MEDICAL ANALYSIS REPORT ===")
    if df.empty:
        print("No astronauts found in database.")
        return

    for _, row in df.iterrows():
        full_name = printable(f"{row[LAST_NAME_COLUMN]} {row[FIRST_NAME_COLUMN]}")
        print(f"\nAstronaut: {full_name}")
        results = analyze_row(row)
        for label, status in results.items():
            if label == "Overall Status":
                print(f"  --> Overall Status: [{status}]")
            else:
                print(f"  - {label}: {status}")
        print("-" * 40)


if __name__ == "__main__":
    main()
