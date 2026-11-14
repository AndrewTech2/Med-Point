"""Shared types for the recommendation system (calculations_extended.md, "Recommendation system").

This module only defines data types; the rules table and its thresholds live in
recommendation_rules.py and the evaluation engine lives in recommendations.py.
All thresholds are informational: confirm them with the flight surgeon / medical team.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import MappingProxyType

from calculations import Sex
from Caracteristici import Characteristic


class Status(IntEnum):
    """Status levels. UNKNOWN (-1) means the rule could not be evaluated; it never counts as OK."""

    UNKNOWN = -1
    OK = 0
    WATCH = 1
    ACTION = 2
    URGENT = 3


class BodySystem(Enum):
    """Columns of the influence map."""

    HEART_VESSELS = "Heart & vessels"
    BRAIN = "Brain & nervous system"
    MUSCLES = "Muscles"
    BONES = "Bones"
    EYES = "Eyes"
    KIDNEYS_FLUIDS = "Kidneys & fluids"
    METABOLISM = "Metabolism & hormones"
    BLOOD = "Blood"
    IMMUNE = "Immune"
    SLEEP = "Sleep & circadian"


# Fixed system order used to sort recommendations ("Priority and ordering", step 3).
SYSTEM_ORDER: tuple[BodySystem, ...] = (
    BodySystem.HEART_VESSELS,
    BodySystem.BRAIN,
    BodySystem.EYES,
    BodySystem.BLOOD,
    BodySystem.METABOLISM,
    BodySystem.BONES,
    BodySystem.MUSCLES,
    BodySystem.KIDNEYS_FLUIDS,
    BodySystem.SLEEP,
    BodySystem.IMMUNE,
)


class MissionPhase(Enum):
    ADAPTATION = "adaptation"
    LONG_DURATION = "long-duration"
    RETURN = "return"
    UNKNOWN = "unknown"


ALL_PHASES: tuple[MissionPhase, ...] = (
    MissionPhase.ADAPTATION,
    MissionPhase.LONG_DURATION,
    MissionPhase.RETURN,
)


class ExtraInput(Enum):
    """Optional inputs that are not among the 14 stored characteristics. Value = display label."""

    HYPERTENSIVE_SYMPTOMS = "Hypertensive crisis symptoms (yes/no)"
    ORTHOSTATIC_SYMPTOMS = "Orthostatic symptoms on standing (yes/no)"
    SYSTOLIC_SUPINE = "Systolic BP supine (mmHg)"
    SYSTOLIC_STANDING = "Systolic BP after standing 10 min (mmHg)"
    HEART_RATE_SUPINE = "Heart rate supine (bpm)"
    HEART_RATE_STANDING = "Heart rate after standing 10 min (bpm)"
    VO2_MAX = "VO2max now (mL/kg/min)"
    VO2_MAX_PREFLIGHT = "VO2max preflight (mL/kg/min)"
    HEMOGLOBIN_G_DL = "Hemoglobin (g/dL)"
    HEMOGLOBIN_LAB_LOWER_LIMIT_G_DL = "Hemoglobin lab lower limit (g/dL)"
    HBA1C_PERCENT = "HbA1c (%)"
    ENERGY_DEFICIT_DAYS = "Consecutive days with intake below TDEE"
    SEX = "Sex (M/F)"
    WAIST_CIRCUMFERENCE_CM = "Waist circumference (cm)"
    MUSCLE_MASS_PERCENTAGE_PREFLIGHT = "Muscle mass percentage preflight (%)"
    GRIP_STRENGTH_KG = "Grip strength (kg)"
    BONE_DENSITY_PREFLIGHT = "Bone density preflight (g/cm²)"
    MONTHS_IN_FLIGHT = "Months in flight"
    T_SCORE = "Bone density T-score"
    VITAMIN_D_NG_ML = "Vitamin D (ng/mL)"
    MISSION_PHASE = "Mission phase (--phase)"
    SLEEP_HOURS_HISTORY = "Daily sleep hours, last 7 days"
    TIME_IN_BED_HOURS = "Time in bed (hours)"
    SLEEP_LATENCY_MIN = "Sleep latency (min)"
    PVT_LAPSES = "PVT lapses (count)"
    PVT_LAPSES_BASELINE = "PVT lapses baseline (count)"
    PSS10_ANSWERS = "PSS-10 answers (10 items, 0-4)"
    HRV_RMSSD_MS = "HRV RMSSD (ms)"
    HRV_RMSSD_BASELINE_MS = "HRV RMSSD baseline (ms)"
    PRIOR_CAREER_DOSE_MSV = "Career radiation dose before this mission (mSv)"
    SANS_NEW_FINDINGS = "New SANS eye findings (yes/no)"
    SANS_GRADE_WORSENED = "SANS grade worsened since last exam (yes/no)"


InputKey = Characteristic | ExtraInput
InputValue = float | int | bool | str | Sex | tuple[float, ...] | None


@dataclass(frozen=True)
class RuleContext:
    """Validated inputs for one astronaut. Missing or invalid inputs are absent from `values`.

    When the phase is known, the engine also stores it under ExtraInput.MISSION_PHASE.
    """

    values: Mapping[InputKey, InputValue]
    phase: MissionPhase = MissionPhase.UNKNOWN

    def get(self, key: InputKey) -> InputValue:
        """Return the input value or None when it is missing."""
        return self.values.get(key)


def make_context(
    values: Mapping[InputKey, InputValue], phase: MissionPhase = MissionPhase.UNKNOWN
) -> RuleContext:
    """Build a RuleContext from a copy of `values` (None entries dropped, read-only view)."""
    cleaned = {key: value for key, value in values.items() if value is not None}
    if phase is not MissionPhase.UNKNOWN:
        cleaned = {**cleaned, ExtraInput.MISSION_PHASE: phase.value}
    return RuleContext(values=MappingProxyType(cleaned), phase=phase)


# An assessor returns OK / WATCH / ACTION / URGENT, or UNKNOWN when it cannot decide
# because inputs are missing. It may raise ValueError / TypeError on bad data; the
# engine turns that into UNKNOWN.
Assessor = Callable[[RuleContext], Status]


@dataclass(frozen=True)
class Rule:
    id: str  # "CV-1"
    variable: str  # "Blood pressure"
    condition: str  # human-readable condition with the thresholds, e.g. "SBP > 180 or DBP > 120 with symptoms"
    status: Status  # highest status this rule can give
    protects: tuple[BodySystem, ...]
    actions: tuple[str, ...]  # one or more action items; identical texts are merged across rules
    source: str  # "[S14, S15]" or "[design]"
    inputs: tuple[InputKey, ...]  # every input the rule may read
    phases: tuple[MissionPhase, ...]  # mission phases where the rule is most relevant
    assess: Assessor
