"""Extra calculations derived from the astronaut characteristics.

Calculations 1-13 are in Calcule.md. Calculations 14-35 are in calculations_extended.md.
The functions are pure (no reading or writing), except load_astronauts, which only reads.
All thresholds are informational and must be confirmed by the mission medical team.
"""

import math
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from enum import Enum
from typing import NamedTuple

from Caracteristici import CHARACTERISTIC_DEFINITIONS, DB_PATH, Characteristic, column_name

RECOMMENDED_SLEEP_MIN_HOURS = 7.0  # NSF/AASM, adults (Calcule.md 9)
CAREER_RADIATION_LIMIT_MSV = 600.0  # NASA career limit (calculations_extended.md 32)
PVT_LAPSE_THRESHOLD_MS = 500.0  # 10-minute PVT (calculations_extended.md 31)
PVT_B_LAPSE_THRESHOLD_MS = 355.0  # brief PVT-B (calculations_extended.md 31)
HR_RECOVERY_ABNORMAL_BPM = 12.0  # bpm (calculations_extended.md 17)
VO2_MIN_PERCENT = 80.0  # % of the preflight value (calculations_extended.md 18)
MIN_ADULT_AGE = 18


class Sex(Enum):
    M = "M"
    F = "F"


class ActivityLevel(Enum):
    """Activity factors for TDEE (calculations_extended.md 22); the values are unverified."""

    SEDENTARY = 1.2
    LIGHTLY_ACTIVE = 1.375
    MODERATELY_ACTIVE = 1.55
    VERY_ACTIVE = 1.725
    EXTRA_ACTIVE = 1.9


GRIP_STRENGTH_MIN_KG = {Sex.M: 27.0, Sex.F: 16.0}  # EWGSOP2 (calculations_extended.md 26)


class OrthostaticResponse(NamedTuple):
    delta_systolic: float
    delta_heart_rate: float


def _require_positive(value: float, name: str) -> None:
    # `not value > 0` also rejects NaN.
    if not value > 0:
        raise ValueError(f"{name} must be positive.")


def _require_valid_blood_pressure(systolic: float, diastolic: float) -> None:
    _require_positive(diastolic, "Diastolic pressure")
    if systolic <= diastolic:
        raise ValueError("Systolic pressure must be higher than diastolic pressure.")


# --- Body and composition -----------------------------------------------------


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Calcule.md 1: BMI = weight / height(m)², rounded to one decimal."""
    _require_positive(weight_kg, "Weight")
    _require_positive(height_cm, "Height")
    return round(weight_kg / (height_cm / 100) ** 2, 1)


def fat_mass_kg(weight_kg: float, body_fat_pct: float) -> float:
    """Calcule.md 2."""
    return weight_kg * body_fat_pct / 100


def lean_mass_kg(weight_kg: float, body_fat_pct: float) -> float:
    """Calcule.md 3: mass without fat."""
    return weight_kg - fat_mass_kg(weight_kg, body_fat_pct)


def muscle_mass_kg(weight_kg: float, muscle_mass_pct: float) -> float:
    """Calcule.md 4."""
    return weight_kg * muscle_mass_pct / 100


def bmi_category(bmi: float) -> str:
    """Calcule.md 5 (WHO)."""
    if bmi < 18.5:
        return "underweight"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    return "obese"


def ffmi(lean_mass: float, height_cm: float) -> float:
    """calculations_extended.md 20: fat-free mass index."""
    _require_positive(height_cm, "Height")
    return round(lean_mass / (height_cm / 100) ** 2, 2)


def ffmi_normalized(lean_mass: float, height_cm: float) -> float:
    """calculations_extended.md 20: FFMI normalised to 1.8 m (Kouri 1995)."""
    height_m = height_cm / 100
    return round(ffmi(lean_mass, height_cm) + 6.1 * (1.8 - height_m), 2)


def waist_to_height_ratio(waist_cm: float, height_cm: float) -> float:
    """calculations_extended.md 23: about 0.5 is the usual cut-off for adults."""
    _require_positive(height_cm, "Height")
    return round(waist_cm / height_cm, 2)


def basal_metabolic_rate(weight_kg: float, height_cm: float, age: float, sex: Sex) -> float:
    """calculations_extended.md 21: Mifflin-St Jeor, in kcal/day (accuracy about ±10%)."""
    adjustment = 5 if sex is Sex.M else -161
    return round(10 * weight_kg + 6.25 * height_cm - 5 * age + adjustment, 1)


def total_energy_expenditure(bmr: float, activity: ActivityLevel) -> float:
    """calculations_extended.md 22: TDEE = BMR × activity factor."""
    return round(bmr * activity.value, 1)


def energy_balance(intake_kcal: float, tdee: float) -> float:
    """calculations_extended.md 22: negative = energy deficit."""
    return round(intake_kcal - tdee, 1)


# --- Heart, blood pressure, glucose -------------------------------------------


def pulse_category(pulse: float) -> str:
    """Calcule.md 7 (adult at rest)."""
    if pulse < 60:
        return "bradycardia"
    if pulse <= 100:
        return "normal"
    return "tachycardia"


def blood_pressure_category(systolic: float, diastolic: float) -> str:
    """Calcule.md 6 and calculations_extended.md 35: the most severe of the two values applies."""
    _require_valid_blood_pressure(systolic, diastolic)
    if systolic > 180 or diastolic > 120:
        return "hypertensive crisis"
    if systolic < 90 or diastolic < 60:
        return "low"
    if systolic >= 130 or diastolic >= 80:
        return "high (hypertension)"
    if systolic >= 120:
        return "elevated"
    return "normal"


def evaluate_hypertensive_crisis(
    systolic: float, diastolic: float, has_symptoms: bool
) -> str:
    """calculations_extended.md 35: crisis = systolic >180 and/or diastolic >120 (AHA)."""
    _require_valid_blood_pressure(systolic, diastolic)
    if systolic <= 180 and diastolic <= 120:
        return "no crisis"
    if has_symptoms:
        return "MEDICAL EMERGENCY (hypertensive crisis with symptoms)"
    return "hypertensive crisis without symptoms (medical reassessment)"


def mean_arterial_pressure(systolic: float, diastolic: float) -> float:
    """calculations_extended.md 14: MAP = dia + (sys - dia) / 3."""
    _require_valid_blood_pressure(systolic, diastolic)
    return round(diastolic + (systolic - diastolic) / 3, 1)


def pulse_pressure(systolic: float, diastolic: float) -> float:
    """calculations_extended.md 15."""
    _require_valid_blood_pressure(systolic, diastolic)
    return systolic - diastolic


def glucose_category(glucose_mg_dl: float) -> str:
    """Calcule.md 8 and calculations_extended.md 34 (ADA, fasting values)."""
    if glucose_mg_dl < 54:
        return "level 2 hypoglycemia"
    if glucose_mg_dl < 70:
        return "level 1 hypoglycemia"
    if glucose_mg_dl < 100:
        return "normal"
    if glucose_mg_dl < 126:
        return "prediabetes"
    return "high"


def max_heart_rate_220(age: float) -> float:
    """Calcule.md 13 (the 220 - age formula)."""
    return 220 - age


def max_heart_rate_tanaka(age: float) -> float:
    """calculations_extended.md 16."""
    return round(208 - 0.7 * age, 1)


def percent_max_heart_rate(pulse: float, max_heart_rate: float) -> float:
    """calculations_extended.md 16: pulse as a percentage of the maximum heart rate."""
    _require_positive(max_heart_rate, "Maximum heart rate")
    return round(pulse / max_heart_rate * 100, 1)


def heart_rate_recovery(final_exercise_pulse: float, pulse_after_1_min: float) -> float:
    """calculations_extended.md 17."""
    return final_exercise_pulse - pulse_after_1_min


def heart_rate_recovery_abnormal(recovery: float) -> bool:
    return recovery <= HR_RECOVERY_ABNORMAL_BPM


def vo2_percent_of_preflight(vo2_now: float, vo2_preflight: float) -> float:
    """calculations_extended.md 18: requires a reference value from before flight."""
    _require_positive(vo2_preflight, "Preflight VO2max")
    return round(vo2_now / vo2_preflight * 100, 1)


def vo2_below_threshold(vo2_percent: float) -> bool:
    return vo2_percent < VO2_MIN_PERCENT


def orthostatic_response(
    systolic_supine: float, hr_supine: float, systolic_standing: float, hr_standing: float
) -> OrthostaticResponse:
    """calculations_extended.md 19: differences only; exact thresholds are not verified."""
    return OrthostaticResponse(
        delta_systolic=systolic_standing - systolic_supine,
        delta_heart_rate=hr_standing - hr_supine,
    )


# --- Bones and muscles --------------------------------------------------------


def t_score_category(t_score: float) -> str:
    """calculations_extended.md 24 (WHO)."""
    if t_score >= -1.0:
        return "normal"
    if t_score > -2.5:
        return "osteopenia"
    return "osteoporosis"


def bone_loss_rate(bmd_preflight: float, bmd_now: float, months: float) -> float:
    """calculations_extended.md 25: percentage loss per month."""
    _require_positive(bmd_preflight, "Preflight BMD")
    _require_positive(months, "Number of months")
    return round((bmd_preflight - bmd_now) / bmd_preflight * 100 / months, 2)


def grip_strength_low(grip_kg: float, sex: Sex) -> bool:
    """calculations_extended.md 26 (EWGSOP2)."""
    return grip_kg < GRIP_STRENGTH_MIN_KG[sex]


# --- Sleep, stress, cognition, radiation --------------------------------------


def recommended_sleep_minimum(age: float) -> float:
    """calculations_extended.md 28: 7 h minimum for adults (NSF)."""
    if age < MIN_ADULT_AGE:
        raise ValueError("The sleep recommendation is only defined for adults.")
    return RECOMMENDED_SLEEP_MIN_HOURS


def sleep_deficit(hours_slept: float, age: float) -> float:
    """Calcule.md 9: positive = deficit, negative = surplus."""
    return recommended_sleep_minimum(age) - hours_slept


def cumulative_sleep_debt(hours_per_day: Sequence[float], age: float) -> float:
    """calculations_extended.md 28: sum of the daily deficits over a window (e.g. 7 days)."""
    if not hours_per_day:
        raise ValueError("At least one day of data is required.")
    return sum(sleep_deficit(hours, age) for hours in hours_per_day)


def sleep_efficiency(hours_slept: float, time_in_bed: float) -> float:
    """calculations_extended.md 27: percentage of time in bed spent asleep (85% or more is usual)."""
    _require_positive(time_in_bed, "Time in bed")
    if hours_slept > time_in_bed:
        raise ValueError("Hours slept cannot exceed the time spent in bed.")
    return round(hours_slept / time_in_bed * 100, 1)


def stress_category(level: float) -> str:
    """Calcule.md 10 and calculations_extended.md 33: proposed bands (design), no official source."""
    if not 1 <= level <= 10:
        raise ValueError("Stress level must be between 1 and 10.")
    if level < 4:
        return "low"
    if level < 7:
        return "moderate"
    return "high"


def pss10_score(answers: Sequence[int]) -> int:
    """calculations_extended.md 30: 10 answers scored 0-4; items 4, 5, 7 and 8 are reversed."""
    if len(answers) != 10 or not all(0 <= a <= 4 for a in answers):
        raise ValueError("The PSS-10 needs 10 answers between 0 and 4.")
    reversed_items = {3, 4, 6, 7}  # 0-based indexes for items 4, 5, 7, 8
    return sum(4 - a if i in reversed_items else a for i, a in enumerate(answers))


def pss10_category(score: int) -> str:
    """calculations_extended.md 30: widely used bands, but not official."""
    if score <= 13:
        return "low"
    if score <= 26:
        return "moderate"
    return "high"


def hrv_rmssd(rr_intervals_ms: Sequence[float]) -> float:
    """calculations_extended.md 29: RMSSD from RR intervals (ms)."""
    if len(rr_intervals_ms) < 2:
        raise ValueError("At least 2 RR intervals are required.")
    differences = [b - a for a, b in zip(rr_intervals_ms, rr_intervals_ms[1:])]
    return round(math.sqrt(sum(d * d for d in differences) / len(differences)), 2)


def pvt_lapses(
    reaction_times_ms: Sequence[float], threshold_ms: float = PVT_LAPSE_THRESHOLD_MS
) -> int:
    """calculations_extended.md 31: number of reactions at or above the threshold."""
    return sum(1 for t in reaction_times_ms if t >= threshold_ms)


def career_radiation_dose(mission_doses_msv: Sequence[float]) -> float:
    """calculations_extended.md 32."""
    if any(d < 0 for d in mission_doses_msv):
        raise ValueError("Doses cannot be negative.")
    return sum(mission_doses_msv)


def radiation_limit_percent(career_dose_msv: float) -> float:
    """calculations_extended.md 32: percentage of the NASA career limit (600 mSv)."""
    return round(career_dose_msv / CAREER_RADIATION_LIMIT_MSV * 100, 1)


# --- Aggregation from the stored characteristics ------------------------------


def calculate_from_characteristics(
    values: dict[Characteristic, float],
) -> dict[str, float | str]:
    """Calculate what can be derived from the stored characteristics (no input is changed)."""
    c = Characteristic
    weight, height = values[c.BODY_WEIGHT], values[c.HEIGHT]
    age = values[c.AGE]
    systolic = values[c.SYSTOLIC_BLOOD_PRESSURE]
    diastolic = values[c.DIASTOLIC_BLOOD_PRESSURE]
    lean = lean_mass_kg(weight, values[c.BODY_FAT_PERCENTAGE])
    return {
        "bmi_calculated": calculate_bmi(weight, height),
        "bmi_category": bmi_category(values[c.BODY_MASS_INDEX]),
        "fat_mass_kg": round(fat_mass_kg(weight, values[c.BODY_FAT_PERCENTAGE]), 1),
        "lean_mass_kg": round(lean, 1),
        "muscle_mass_kg": round(muscle_mass_kg(weight, values[c.MUSCLE_MASS_PERCENTAGE]), 1),
        "ffmi": ffmi(lean, height),
        "ffmi_normalized": ffmi_normalized(lean, height),
        "blood_pressure_category": blood_pressure_category(systolic, diastolic),
        "mean_arterial_pressure": mean_arterial_pressure(systolic, diastolic),
        "pulse_pressure": pulse_pressure(systolic, diastolic),
        "pulse_category": pulse_category(values[c.AVERAGE_HEART_RATE]),
        "glucose_category": glucose_category(values[c.BLOOD_GLUCOSE]),
        "stress_category": stress_category(values[c.STRESS_LEVEL]),
        "sleep_deficit_hours": sleep_deficit(values[c.SLEEP_HOURS], age),
        "max_heart_rate_220": max_heart_rate_220(age),
        "max_heart_rate_tanaka": max_heart_rate_tanaka(age),
    }


def load_astronauts(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str], dict[Characteristic, float | None]]:
    """Read each astronaut and their latest measurement record."""
    demographic_characteristics = {
        Characteristic.AGE: "age",
        Characteristic.BODY_WEIGHT: "weight",
        Characteristic.HEIGHT: "height",
    }
    selections = []
    for definition in CHARACTERISTIC_DEFINITIONS:
        characteristic = definition.characteristic
        if characteristic in demographic_characteristics:
            selections.append(
                f"a.{demographic_characteristics[characteristic]} AS "
                f"{column_name(characteristic)}"
            )
        else:
            selections.append(
                f"m.{column_name(characteristic)} AS {column_name(characteristic)}"
            )
    rows = conn.execute(
        f"""SELECT a.last_name, a.first_name, {", ".join(selections)}
        FROM astronauts AS a
        LEFT JOIN measurement_history AS m
            ON m.id = (
                SELECT latest.id
                FROM measurement_history AS latest
                WHERE latest.astronaut_id = a.id
                ORDER BY latest.recorded_at DESC, latest.id DESC
                LIMIT 1
            )
        ORDER BY a.id"""
    ).fetchall()
    result: dict[tuple[str, str], dict[Characteristic, float | None]] = {}
    for row in rows:
        result[(row[0], row[1])] = {
            definition.characteristic: row[index + 2]
            for index, definition in enumerate(CHARACTERISTIC_DEFINITIONS)
        }
    return result


def main() -> None:
    sys.stdout.reconfigure(errors="replace")
    if not DB_PATH.exists():
        print(f"Database {DB_PATH.name} not found. Run Caracteristici.py first.")
        return
    with closing(sqlite3.connect(DB_PATH)) as conn:
        astronauts = load_astronauts(conn)
    for (last_name, first_name), values in astronauts.items():
        print(f"\n{last_name} {first_name}")
        if any(value is None for value in values.values()):
            print("  skipped: some characteristics are missing for this astronaut")
            continue
        for key, result in calculate_from_characteristics(values).items():
            print(f"  {key}: {result}")


if __name__ == "__main__":
    main()
