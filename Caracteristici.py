"""Required characteristics for each astronaut.

The list comes from README.md ("Required characteristics").
Each characteristic has minimum and maximum plausible limits for an adult,
and the entered values are checked against each other for consistency.
"""

import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DB_PATH = Path(__file__).with_name("astronauts.db")
MAX_NAME_LENGTH = 50

# Maximum acceptable difference between entered BMI and BMI calculated from weight and height.
BMI_TOLERANCE = 1.0
# Muscle + fat cannot make up almost the entire body (bones, organs, water, etc.).
MAX_MUSCLE_PLUS_FAT_PERCENTAGE = 90.0


class Characteristic(Enum):
    AGE = "Age"
    BODY_WEIGHT = "Body weight"
    HEIGHT = "Height"
    BODY_MASS_INDEX = "Body mass index"
    AVERAGE_HEART_RATE = "Average heart rate"
    SYSTOLIC_BLOOD_PRESSURE = "Systolic blood pressure"
    DIASTOLIC_BLOOD_PRESSURE = "Diastolic blood pressure"
    MUSCLE_MASS_PERCENTAGE = "Muscle mass percentage"
    BODY_FAT_PERCENTAGE = "Body fat percentage"
    STRESS_LEVEL = "Stress level"
    MISSION_RADIATION_LEVEL = "Mission radiation exposure level"
    BONE_DENSITY_CALCIUM = "Bone density (calcium)"
    BLOOD_GLUCOSE = "Blood glucose"
    SLEEP_HOURS = "Sleep duration"


@dataclass(frozen=True)
class CharacteristicDefinition:
    characteristic: Characteristic
    unit: str
    minimum: float
    maximum: float


@dataclass(frozen=True)
class Inconsistency:
    message: str
    fields: tuple[Characteristic, ...]


CHARACTERISTIC_DEFINITIONS: tuple[CharacteristicDefinition, ...] = (
    CharacteristicDefinition(Characteristic.AGE, "years", 18, 70),
    CharacteristicDefinition(Characteristic.BODY_WEIGHT, "kg", 40, 150),
    CharacteristicDefinition(Characteristic.HEIGHT, "cm", 140, 210),
    CharacteristicDefinition(Characteristic.BODY_MASS_INDEX, "kg/m²", 15, 40),
    CharacteristicDefinition(Characteristic.AVERAGE_HEART_RATE, "bpm", 30, 200),
    CharacteristicDefinition(Characteristic.SYSTOLIC_BLOOD_PRESSURE, "mmHg", 70, 250),
    CharacteristicDefinition(Characteristic.DIASTOLIC_BLOOD_PRESSURE, "mmHg", 40, 150),
    CharacteristicDefinition(Characteristic.MUSCLE_MASS_PERCENTAGE, "%", 20, 60),
    CharacteristicDefinition(Characteristic.BODY_FAT_PERCENTAGE, "%", 3, 50),
    CharacteristicDefinition(Characteristic.STRESS_LEVEL, "scale", 1, 10),
    CharacteristicDefinition(Characteristic.MISSION_RADIATION_LEVEL, "mSv", 0.1, 200),
    CharacteristicDefinition(Characteristic.BONE_DENSITY_CALCIUM, "g/cm²", 0.5, 1.8),
    CharacteristicDefinition(Characteristic.BLOOD_GLUCOSE, "mg/dL", 40, 300),
    CharacteristicDefinition(Characteristic.SLEEP_HOURS, "hours", 2, 12),
)

CHARACTERISTIC_COLUMNS = {
    Characteristic.AGE: "age",
    Characteristic.BODY_WEIGHT: "weight",
    Characteristic.HEIGHT: "height",
    Characteristic.BODY_MASS_INDEX: "bmi",
    Characteristic.AVERAGE_HEART_RATE: "average_pulse",
    Characteristic.SYSTOLIC_BLOOD_PRESSURE: "systolic_pressure",
    Characteristic.DIASTOLIC_BLOOD_PRESSURE: "diastolic_pressure",
    Characteristic.MUSCLE_MASS_PERCENTAGE: "muscle_mass_percentage",
    Characteristic.BODY_FAT_PERCENTAGE: "body_fat_percentage",
    Characteristic.STRESS_LEVEL: "stress_level",
    Characteristic.MISSION_RADIATION_LEVEL: "radiation_levels",
    Characteristic.BONE_DENSITY_CALCIUM: "bone_density",
    Characteristic.BLOOD_GLUCOSE: "glucose",
    Characteristic.SLEEP_HOURS: "sleep_hours",
}


@dataclass(frozen=True)
class HistoryExtra:
    """A measurement stored and graphed per reading but not a required characteristic."""

    key: str  # name used in the export and in metric_categories.js
    label: str
    unit: str
    minimum: float
    maximum: float
    column: str


HISTORY_EXTRAS: tuple[HistoryExtra, ...] = (
    HistoryExtra("VO2_MAX", "VO2max", "mL/kg/min", 10, 90, "vo2_max"),
    HistoryExtra("HEART_RATE_RECOVERY", "Heart rate recovery", "bpm", 0, 80, "hr_recovery"),
)


def format_limits(definition: CharacteristicDefinition) -> str:
    return f"{definition.minimum:g} - {definition.maximum:g} {definition.unit}"


def is_within_limits(definition: CharacteristicDefinition, value: float) -> bool:
    # NaN and infinity are rejected automatically: comparisons with NaN are False.
    return definition.minimum <= value <= definition.maximum


def read_value(definition: CharacteristicDefinition) -> float:
    """Prompt for a numeric value within the defined limits until it is valid."""
    print(f"\nLimits: {format_limits(definition)}")
    prompt = f"{definition.characteristic.value}: "
    while True:
        text = input(prompt)
        try:
            value = float(text.strip().replace(",", "."))
        except ValueError:
            print("Please enter a valid number.")
            continue
        if not is_within_limits(definition, value):
            print(f"The value must be between {format_limits(definition)}.")
            continue
        return value


def check_consistency(values: dict[Characteristic, float]) -> list[Inconsistency]:
    """Check whether the values are compatible with each other."""
    problems: list[Inconsistency] = []
    systolic = values[Characteristic.SYSTOLIC_BLOOD_PRESSURE]
    diastolic = values[Characteristic.DIASTOLIC_BLOOD_PRESSURE]
    if systolic <= diastolic:
        problems.append(
            Inconsistency(
                "Systolic pressure must be higher than diastolic pressure.",
                (Characteristic.SYSTOLIC_BLOOD_PRESSURE, Characteristic.DIASTOLIC_BLOOD_PRESSURE),
            )
        )

    body_weight = values[Characteristic.BODY_WEIGHT]
    height_m = values[Characteristic.HEIGHT] / 100
    bmi = values[Characteristic.BODY_MASS_INDEX]
    calculated_bmi = body_weight / height_m**2
    if abs(bmi - calculated_bmi) > BMI_TOLERANCE:
        problems.append(
            Inconsistency(
                f"Entered BMI ({bmi:.1f}) does not match body weight and height "
                f"(calculated: {calculated_bmi:.1f}).",
                (
                    Characteristic.BODY_WEIGHT,
                    Characteristic.HEIGHT,
                    Characteristic.BODY_MASS_INDEX,
                ),
            )
        )

    muscle_percentage = values[Characteristic.MUSCLE_MASS_PERCENTAGE]
    fat_percentage = values[Characteristic.BODY_FAT_PERCENTAGE]
    if muscle_percentage + fat_percentage > MAX_MUSCLE_PLUS_FAT_PERCENTAGE:
        problems.append(
            Inconsistency(
                f"Muscle ({muscle_percentage:g}%) + fat ({fat_percentage:g}%) exceed "
                f"{MAX_MUSCLE_PLUS_FAT_PERCENTAGE:g}% of the body.",
                (
                    Characteristic.MUSCLE_MASS_PERCENTAGE,
                    Characteristic.BODY_FAT_PERCENTAGE,
                ),
            )
        )
    return problems


def introduce_characteristics() -> dict[Characteristic, float]:
    """Ask for all characteristics, then re-enter only the inconsistent fields."""
    values = {
        definition.characteristic: read_value(definition)
        for definition in CHARACTERISTIC_DEFINITIONS
    }
    while problems := check_consistency(values):
        for problem in problems:
            print(f"Error: {problem.message}")
        fields_to_reenter = {field for problem in problems for field in problem.fields}
        print("Please re-enter the affected values:")
        for definition in CHARACTERISTIC_DEFINITIONS:
            if definition.characteristic in fields_to_reenter:
                values = {
                    **values,
                    definition.characteristic: read_value(definition),
                }
    return values


def column_name(characteristic: Characteristic) -> str:
    return CHARACTERISTIC_COLUMNS[characteristic]


def read_name(label: str) -> str:
    """Prompt for a name (letters, spaces, hyphens) and normalize it."""
    while True:
        text = " ".join(input(f"{label}: ").split())
        if not text:
            print("The name cannot be empty.")
        elif len(text) > MAX_NAME_LENGTH:
            print(f"Maximum {MAX_NAME_LENGTH} characters.")
        elif not all(ch.isalpha() or ch in " -" for ch in text):
            print("Use only letters, spaces, and hyphens.")
        else:
            return text.title()


# Stored on every measurement row too, so their history is kept (the astronauts table
# only holds the current value).
HISTORY_DEMOGRAPHICS = (Characteristic.AGE, Characteristic.BODY_WEIGHT, Characteristic.HEIGHT)


def create_table(conn: sqlite3.Connection) -> None:
    """Create the English-schema tables if missing and add the history columns to old ones."""
    with conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS astronauts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER,
    height REAL,
    weight REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (first_name, last_name)
)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS measurement_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id INTEGER NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    average_pulse REAL,
    systolic_pressure REAL,
    diastolic_pressure REAL,
    bmi REAL,
    glucose REAL,
    sleep_hours REAL,
    stress_level REAL,
    muscle_mass_percentage REAL,
    body_fat_percentage REAL,
    radiation_levels REAL,
    bone_density REAL,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts (id) ON DELETE CASCADE
)"""
        )
        existing = {row[1] for row in conn.execute("PRAGMA table_info(measurement_history)")}
        for characteristic in HISTORY_DEMOGRAPHICS:
            column = column_name(characteristic)
            if column not in existing:
                conn.execute(f"ALTER TABLE measurement_history ADD COLUMN {column} REAL")
        for extra in HISTORY_EXTRAS:
            if extra.column not in existing:
                conn.execute(f"ALTER TABLE measurement_history ADD COLUMN {extra.column} REAL")


def extra_series(
    conn: sqlite3.Connection, astronaut_id: int, extra: HistoryExtra
) -> list[tuple[str, float]]:
    """(recorded_at, value) of one extra, oldest first; empty for old databases without the column."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(measurement_history)")}
    if extra.column not in existing:
        return []
    rows = conn.execute(
        f"""SELECT recorded_at, {extra.column} FROM measurement_history
        WHERE astronaut_id = ? AND {extra.column} IS NOT NULL
        ORDER BY recorded_at, id""",  # column name comes from HISTORY_EXTRAS, never from input
        (astronaut_id,),
    ).fetchall()
    return [(when, value) for when, value in rows]


def astronaut_exists(conn: sqlite3.Connection, last_name: str, first_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM astronauts WHERE last_name = ? AND first_name = ?",
        (last_name, first_name),
    ).fetchone()
    return row is not None


def save_astronaut(
    conn: sqlite3.Connection,
    last_name: str,
    first_name: str,
    values: dict[Characteristic, float],
) -> None:
    """Upsert astronaut demographics and append a measurement record."""
    age = values[Characteristic.AGE]
    height = values[Characteristic.HEIGHT]
    weight = values[Characteristic.BODY_WEIGHT]
    with conn:
        existing_astronaut = conn.execute(
            "SELECT id FROM astronauts WHERE first_name = ? AND last_name = ?",
            (first_name, last_name),
        ).fetchone()
        if existing_astronaut is None:
            cursor = conn.execute(
                """INSERT INTO astronauts (first_name, last_name, age, height, weight)
                VALUES (?, ?, ?, ?, ?)""",
                (first_name, last_name, age, height, weight),
            )
            astronaut_id = cursor.lastrowid
        else:
            astronaut_id = existing_astronaut[0]
            conn.execute(
                """UPDATE astronauts SET age = ?, height = ?, weight = ?
                WHERE id = ?""",
                (age, height, weight, astronaut_id),
            )
        measurement_characteristics = [d.characteristic for d in CHARACTERISTIC_DEFINITIONS]
        measurement_columns = [
            column_name(characteristic) for characteristic in measurement_characteristics
        ]
        columns_sql = ", ".join(["astronaut_id", *measurement_columns])
        placeholders = ", ".join("?" for _ in range(len(measurement_columns) + 1))
        measurement_values = tuple(
            values[characteristic] for characteristic in measurement_characteristics
        )
        conn.execute(
            f"INSERT INTO measurement_history ({columns_sql}) VALUES ({placeholders})",
            (astronaut_id, *measurement_values),
        )


def confirm(question: str) -> bool:
    return input(f"{question} (y/n): ").strip().lower() in ("y", "yes")


def main() -> None:
    last_name = read_name("Last name")
    first_name = read_name("First name")
    with closing(sqlite3.connect(DB_PATH)) as conn:
        create_table(conn)
        if astronaut_exists(conn, last_name, first_name) and not confirm(
            "The astronaut already exists. Overwrite the data?"
        ):
            print("No changes were made.")
            return
        values = introduce_characteristics()
        save_astronaut(conn, last_name, first_name, values)
    print(f"\nData saved for {last_name} {first_name} in {DB_PATH.name}:")
    for characteristic, value in values.items():
        print(f"  {characteristic.value}: {value:g}")


if __name__ == "__main__":
    # Avoid blocking terminals that cannot display diacritics (e.g., cp1252).
    sys.stdout.reconfigure(errors="replace")
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nInput was cancelled.")
        raise SystemExit(1)
    except sqlite3.Error as error:
        print(f"Database error: {error}")
        raise SystemExit(1)
