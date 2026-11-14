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

DB_PATH = Path(__file__).with_name("astronauti.db")
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
    return characteristic.name.lower()


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


def update_schema(conn: sqlite3.Connection) -> None:
    """Add the new columns to an existing table without destroying the data."""
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(astronauti)").fetchall()
    }
    for definition in CHARACTERISTIC_DEFINITIONS:
        new_column_name = column_name(definition.characteristic)
        if new_column_name in existing_columns:
            continue
        with conn:
            conn.execute(
                f"ALTER TABLE astronauti ADD COLUMN {new_column_name} REAL "
                f"CHECK ({new_column_name} BETWEEN {definition.minimum:g} AND {definition.maximum:g})"
            )


def create_table(conn: sqlite3.Connection) -> None:
    """Create the table; the limits from CHARACTERISTIC_DEFINITIONS are enforced in the database as well."""
    columns = ",\n    ".join(
        f"{column_name(definition.characteristic)} REAL NOT NULL "
        f"CHECK ({column_name(definition.characteristic)} "
        f"BETWEEN {definition.minimum:g} AND {definition.maximum:g})"
        for definition in CHARACTERISTIC_DEFINITIONS
    )
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS astronauti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nume TEXT NOT NULL,
    prenume TEXT NOT NULL,
    {columns},
    UNIQUE (nume, prenume)
)"""
        )
    update_schema(conn)


def astronaut_exists(conn: sqlite3.Connection, last_name: str, first_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM astronauti WHERE nume = ? AND prenume = ?", (last_name, first_name)
    ).fetchone()
    return row is not None


def save_astronaut(
    conn: sqlite3.Connection,
    last_name: str,
    first_name: str,
    values: dict[Characteristic, float],
) -> None:
    """Insert the astronaut or update their values if they already exist."""
    columns = [column_name(definition.characteristic) for definition in CHARACTERISTIC_DEFINITIONS]
    column_list = ", ".join(["nume", "prenume", *columns])
    placeholders = ", ".join("?" * (len(columns) + 2))
    updates = ", ".join(f"{column} = excluded.{column}" for column in columns)
    params = (last_name, first_name, *(values[definition.characteristic] for definition in CHARACTERISTIC_DEFINITIONS))
    with conn:
        conn.execute(
            f"INSERT INTO astronauti ({column_list}) VALUES ({placeholders}) "
            f"ON CONFLICT(nume, prenume) DO UPDATE SET {updates}",
            params,
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
