import sqlite3
from pathlib import Path

import pandas as pd


# Names used by the existing database schema (the schema itself uses Romanian identifiers).
DB_FILE = "astronauti.db"
TABLE_NAME = "astronauti"
LAST_NAME_COLUMN = "nume"
FIRST_NAME_COLUMN = "prenume"
PULSE_COLUMN = "puls_mediu"
SYSTOLIC_COLUMN = "presiune_sistolica"
BMI_COLUMN = "indice_masa_corporala"
RADIATION_COLUMN = "nivele_radiatie"
BONE_DENSITY_COLUMN = "densitate_osoasa_calciu"


def migrate_database(db_path: str | Path = DB_FILE, table_name: str = TABLE_NAME) -> None:
    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
        for column_name in (RADIATION_COLUMN, BONE_DENSITY_COLUMN):
            if column_name not in columns:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} REAL")
        conn.commit()


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
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def main(db_path: str | Path = DB_FILE) -> None:
    migrate_database(db_path)
    df = load_data(db_path)

    print("=== ASTRONAUT MEDICAL ANALYSIS REPORT ===")
    if df.empty:
        print("No astronauts found in database.")
        return

    for _, row in df.iterrows():
        full_name = f"{row[LAST_NAME_COLUMN]} {row[FIRST_NAME_COLUMN]}"
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
