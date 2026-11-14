"""Fictional demo astronauts for the terminal dashboard.

ALL DATA HERE ARE FICTIONAL. The names and values are invented to exercise the
recommendation system (one overall OK, WATCH, ACTION, URGENT and one incomplete
record); they describe no real person. Thresholds used by the rules are
informational: confirm them with the flight surgeon / medical team.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from calculations import Sex
from Caracteristici import Characteristic as C
from recommendation_types import ExtraInput as E
from recommendation_types import InputKey, InputValue, MissionPhase

_HEALTHY_PSS10: tuple[float, ...] = (1, 1, 1, 3, 3, 1, 3, 3, 1, 1)  # score 10
_HEALTHY_SLEEP_WEEK: tuple[float, ...] = (7.5, 7.8, 8.0, 7.6, 7.9, 7.7, 7.8)

_HEALTHY_CORE: Mapping[InputKey, InputValue] = MappingProxyType({
    C.AGE: 42,
    C.BODY_WEIGHT: 78,
    C.HEIGHT: 180,
    C.BODY_MASS_INDEX: 24.1,
    C.AVERAGE_HEART_RATE: 65,
    C.SYSTOLIC_BLOOD_PRESSURE: 118,
    C.DIASTOLIC_BLOOD_PRESSURE: 76,
    C.MUSCLE_MASS_PERCENTAGE: 42,
    C.BODY_FAT_PERCENTAGE: 18,
    C.STRESS_LEVEL: 2,
    C.MISSION_RADIATION_LEVEL: 40,
    C.BONE_DENSITY_CALCIUM: 1.2,
    C.BLOOD_GLUCOSE: 88,
    C.SLEEP_HOURS: 7.8,
})

_HEALTHY_EXTRAS: Mapping[InputKey, InputValue] = MappingProxyType({
    E.SEX: Sex.M,
    E.HYPERTENSIVE_SYMPTOMS: False,
    E.ORTHOSTATIC_SYMPTOMS: False,
    E.SYSTOLIC_SUPINE: 118,
    E.SYSTOLIC_STANDING: 116,
    E.HEART_RATE_SUPINE: 62,
    E.HEART_RATE_STANDING: 74,
    E.VO2_MAX: 44,
    E.VO2_MAX_PREFLIGHT: 46,
    E.HEMOGLOBIN_G_DL: 14.5,
    E.HEMOGLOBIN_LAB_LOWER_LIMIT_G_DL: 13.0,
    E.HBA1C_PERCENT: 5.2,
    E.ENERGY_DEFICIT_DAYS: 0,
    E.WAIST_CIRCUMFERENCE_CM: 82,
    E.MUSCLE_MASS_PERCENTAGE_PREFLIGHT: 42.5,
    E.GRIP_STRENGTH_KG: 45,
    E.BONE_DENSITY_PREFLIGHT: 1.21,
    E.MONTHS_IN_FLIGHT: 6,
    E.T_SCORE: -0.3,
    E.VITAMIN_D_NG_ML: 35,
    E.SLEEP_HOURS_HISTORY: _HEALTHY_SLEEP_WEEK,
    E.TIME_IN_BED_HOURS: 8.2,
    E.SLEEP_LATENCY_MIN: 12,
    E.PVT_LAPSES: 2,
    E.PVT_LAPSES_BASELINE: 2,
    E.PSS10_ANSWERS: _HEALTHY_PSS10,
    E.HRV_RMSSD_MS: 62,
    E.HRV_RMSSD_BASELINE_MS: 65,
    E.PRIOR_CAREER_DOSE_MSV: 120,
    E.SANS_NEW_FINDINGS: False,
    E.SANS_GRADE_WORSENED: False,
})


@dataclass(frozen=True)
class AstronautRecord:
    last_name: str
    first_name: str
    values: Mapping[InputKey, InputValue]
    phase: MissionPhase | None = None
    note: str = ""


def _healthy_with(
    changes: Mapping[InputKey, InputValue], drop: tuple[InputKey, ...] = ()
) -> Mapping[InputKey, InputValue]:
    """Healthy baseline with `changes` applied and `drop` keys removed (new read-only mapping)."""
    merged = {**_HEALTHY_CORE, **_HEALTHY_EXTRAS, **changes}
    return MappingProxyType({k: v for k, v in merged.items() if k not in drop})


_INCOMPLETE_DROP: tuple[InputKey, ...] = (
    C.BLOOD_GLUCOSE,
    C.BODY_FAT_PERCENTAGE,
    C.STRESS_LEVEL,
    C.MISSION_RADIATION_LEVEL,
    C.BONE_DENSITY_CALCIUM,
)

DEMO_ASTRONAUTS: tuple[AstronautRecord, ...] = (
    AstronautRecord(
        "Vega", "Lyra", _healthy_with({}),
        MissionPhase.LONG_DURATION, "Fictional: all healthy, full data",
    ),
    AstronautRecord(
        "Kai", "Orion",
        _healthy_with({
            C.SYSTOLIC_BLOOD_PRESSURE: 132,
            C.SLEEP_HOURS: 6.5,
            C.STRESS_LEVEL: 5,
        }),
        MissionPhase.LONG_DURATION, "Fictional: mildly raised BP, short sleep, moderate stress",
    ),
    AstronautRecord(
        "Nova", "Sirius",
        _healthy_with({
            C.SYSTOLIC_BLOOD_PRESSURE: 85,
            C.DIASTOLIC_BLOOD_PRESSURE: 55,
            C.AVERAGE_HEART_RATE: 108,
            C.SLEEP_HOURS: 5.5,
            C.STRESS_LEVEL: 4,
            E.ORTHOSTATIC_SYMPTOMS: True,
            E.SYSTOLIC_STANDING: 92,
            E.SYSTOLIC_SUPINE: 118,
            E.HEART_RATE_STANDING: 100,
            E.T_SCORE: -2.7,
        }),
        MissionPhase.RETURN, "Fictional: return phase, low BP + fast HR, short sleep, low T-score",
    ),
    AstronautRecord(
        "Draco", "Altair",
        _healthy_with({
            C.BLOOD_GLUCOSE: 50,
            C.SYSTOLIC_BLOOD_PRESSURE: 190,
            C.DIASTOLIC_BLOOD_PRESSURE: 105,
            E.HYPERTENSIVE_SYMPTOMS: True,
            E.SANS_GRADE_WORSENED: True,
        }),
        MissionPhase.LONG_DURATION, "Fictional: severe hypoglycaemia and hypertensive crisis with symptoms",
    ),
    AstronautRecord(
        "Pavo", "Rigel",
        _healthy_with({}, drop=_INCOMPLETE_DROP),
        MissionPhase.ADAPTATION, "Fictional: several core measurements missing",
    ),
    AstronautRecord(
        "Lynx", "Ara",
        _healthy_with({
            C.SLEEP_HOURS: 6.5,
            C.STRESS_LEVEL: 8,
        }),
        MissionPhase.LONG_DURATION,
        "Fictional: short sleep + high stress (combination raises SL-1 and PS-2 one level)",
    ),
)
