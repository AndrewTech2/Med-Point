import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).with_name("astronauti.db")


def migrate_database(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(astronauti)").fetchall()]
    if "nivele_radiatie" not in columns:
        conn.execute(
            "ALTER TABLE astronauti ADD COLUMN nivele_radiatie REAL"
        )
    if "densitate_osoasa_calciu" not in columns:
        conn.execute(
            "ALTER TABLE astronauti ADD COLUMN densitate_osoasa_calciu REAL"
        )


def evaluate_pulse(value: float) -> str:
    if value is None:
        return "Unknown"
    if value < 50 or value > 115:
        return "Critical"
    if (50 <= value < 60) or (100 < value <= 115):
        return "Warning"
    return "Healthy"


def evaluate_systolic(value: float) -> str:
    if value is None:
        return "Unknown"
    if value < 90 or value >= 140:
        return "Critical"
    if 120 < value <= 139:
        return "Warning"
    return "Healthy"


def evaluate_bmi(value: float) -> str:
    if value is None:
        return "Unknown"
    if value < 17.0 or value >= 30.0:
        return "Critical"
    if (17.0 <= value < 18.5) or (25.0 < value <= 29.9):
        return "Warning"
    return "Healthy"


def evaluate_radiation(value: float) -> str:
    if value is None:
        return "Unknown"
    if value > 100:
        return "Critical"
    if 50 < value <= 100:
        return "Warning"
    return "Healthy"


def evaluate_bone_density(value: float) -> str:
    if value is None:
        return "Unknown"
    if value < 0.7 or value > 1.6:
        return "Critical"
    if (0.7 <= value < 0.9) or (1.4 < value <= 1.6):
        return "Warning"
    return "Healthy"


def evaluate_astronaut(row: dict) -> dict:
    results = {
        "Pulse": evaluate_pulse(row.get("puls_mediu")),
        "Systolic Pressure": evaluate_systolic(row.get("presiune_sistolica")),
        "BMI": evaluate_bmi(row.get("indice_masa_corporala")),
    }
    if "nivele_radiatie" in row:
        results["Radiation"] = evaluate_radiation(row.get("nivele_radiatie"))
    if "densitate_osoasa_calciu" in row:
        results["Bone Density"] = evaluate_bone_density(row.get("densitate_osoasa_calciu"))
    return results


def overall_status(results: dict) -> str:
    active_statuses = [status for status in results.values() if status != "Unknown"]
    if "Critical" in active_statuses:
        return "Critical"
    if "Warning" in active_statuses:
        return "Warning"
    return "Healthy"


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        migrate_database(conn)
        df = pd.read_sql_query("SELECT * FROM astronauti", conn)

    print("=== ASTRONAUT MEDICAL ANALYSIS REPORT ===")
    if df.empty:
        print("No astronauts found in database.")
        return

    for _, row in df.iterrows():
        full_name = f"{row['nume']} {row['prenume']}"
        results = evaluate_astronaut(row)
        global_status = overall_status(results)
        print(f"\nAstronaut: {full_name}")
        for indicator, status in results.items():
            print(f"  - {indicator}: {status}")
        print(f"  --> Overall Status: [{global_status}]")
        print("-" * 40)


if __name__ == "__main__":
    main()
