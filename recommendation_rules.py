"""Rules table for the recommendation system (calculations_extended.md, "Recommendation system").

Every threshold below is INFORMATIONAL and must be confirmed with the flight surgeon / medical
team before any operational use. Thresholds marked [design] are project proposals with no
medical source; [unverified] ones come from general references that were not checked against
a primary source.

All thresholds live in ONE block of named constants (below). The assessor functions contain
no numbers of their own. An assessor returns OK / WATCH / ACTION / URGENT, or UNKNOWN when the
inputs needed to decide are missing; it never returns OK when it cannot decide.
"""

import math
import operator
from collections.abc import Callable, Mapping
from types import MappingProxyType

from calculations import (
    BMI_OBESE,
    BMI_UNDERWEIGHT,
    BP_CRISIS_DIASTOLIC,
    BP_CRISIS_SYSTOLIC,
    BP_HIGH_DIASTOLIC,
    BP_HIGH_SYSTOLIC,
    BP_LOW_DIASTOLIC,
    BP_LOW_SYSTOLIC,
    CAREER_RADIATION_LIMIT_MSV,
    GLUCOSE_DIABETES,
    GLUCOSE_LEVEL1_HYPO,
    GLUCOSE_LEVEL2_HYPO,
    GLUCOSE_PREDIABETES,
    RESTING_HR_HIGH,
    RESTING_HR_LOW,
    STRESS_HIGH_MIN,
    STRESS_MODERATE_MIN,
    GRIP_STRENGTH_MIN_KG,
    MIN_ADULT_AGE,
    RECOMMENDED_SLEEP_MIN_HOURS,
    VO2_MIN_PERCENT,
    Sex,
    bone_loss_rate,
    career_radiation_dose,
    cumulative_sleep_debt,
    pss10_score,
    radiation_limit_percent,
    sleep_deficit,
    sleep_efficiency,
    vo2_percent_of_preflight,
    waist_to_height_ratio,
)
from Caracteristici import Characteristic as C
from recommendation_types import (
    ALL_PHASES,
    SYSTEM_ORDER,
    BodySystem,
    ExtraInput as E,
    MissionPhase,
    Rule,
    RuleContext,
    Status,
)

# --- Thresholds (one block) --------------------------------------------------------------
ORTHOSTATIC_SBP_DROP_MMHG = 20  # systolic drop on standing [unverified/design]
ORTHOSTATIC_HR_RISE_BPM = 30  # heart-rate rise on standing [unverified/design]
VO2_WATCH_PERCENT = 90  # % of preflight VO2max, [design] (VO2_MIN_PERCENT comes from calculations)
HBA1C_PREDIABETES = 5.7  # %, [unverified]
HBA1C_DIABETES = 6.5  # %, [unverified]
ENERGY_DEFICIT_MIN_DAYS = 3  # consecutive days below TDEE, [design]
ESSENTIAL_FAT_MAX_PERCENT: Mapping[Sex, float] = MappingProxyType({Sex.M: 5.0, Sex.F: 13.0})  # [design]
HIGH_FAT_PERCENT: Mapping[Sex, float] = MappingProxyType({Sex.M: 25.0, Sex.F: 32.0})  # [S23, S25]
WHTR_HIGH = 0.5  # waist-to-height ratio, [S23, S25]
MUSCLE_DROP_PERCENT = 10  # % drop from preflight muscle mass, [design X]
BONE_LOSS_RATE_MAX = 1.5  # % per month, [design]
T_SCORE_OSTEOPOROSIS = -2.5  # WHO
T_SCORE_NORMAL_MIN = -1.0  # WHO
VITAMIN_D_LOW_NG_ML = 20  # ng/mL, [unverified]
SLEEP_SHORT_HOURS = 6  # h, [S40, S43]
SLEEP_DEBT_MAX_HOURS = 10  # h over the history window, [design Y]
SLEEP_EFFICIENCY_MIN = 85  # %, [unverified]
SLEEP_LATENCY_MAX_MIN = 30  # min, [unverified]
PVT_LAPSE_INCREASE_WATCH = 2  # lapses above baseline, [design]
PVT_LAPSE_INCREASE_ACTION = 5  # lapses above baseline, [design]
PSS10_HIGH_MIN = 27  # PSS-10 score 0-40, [S45, S46]
HRV_DROP_PERCENT = 20  # % drop of RMSSD versus baseline, [design]
RADIATION_WATCH_PERCENT = 50  # % of career limit, [design]
RADIATION_ACTION_PERCENT = 80  # % of career limit, [design]
RADIATION_URGENT_PERCENT = 100  # % of career limit (NASA 600 mSv), [S33, S34]
ESCALATION_WATCH_COUNT = 3  # 3+ WATCH on one system raise it to ACTION [design]
MULTI_SYSTEM_ACTION_COUNT = 2  # ACTION or URGENT on 2+ systems -> multi-system review [design]

# --- Shared action texts (identical strings are merged by the engine) --------------------
ACTION_RESISTANCE_EXERCISE = "Resistance exercise (ARED)"
ACTION_NUTRITION_REVIEW = "Nutrition review"
ACTION_EXERCISE_REVIEW = "Exercise review"
ACTION_MEDICAL_FOLLOW_UP = "Medical follow-up"
ACTION_MEDICAL_REVIEW = "Medical review"
ACTION_SLEEP_SCHEDULE = "Fixed sleep/wake schedule; sleep-promoting lighting"
ACTION_SLEEP_HYGIENE = "Sleep hygiene; scheduled lighting"
ACTION_CONTACT_FLIGHT_SURGEON = "Contact the flight surgeon now"
ACTION_RECHECK_AT_REST = "Recheck at rest"
ACTION_WORKLOAD_REVIEW = "Review workload"
ACTION_AEROBIC_EXERCISE = (
    "Aerobic exercise >= 160 min/week at > 75% peak HR; high-intensity (Sprint) protocol is an option"
)

# --- Helpers -----------------------------------------------------------------------------
_Part = bool | None


def _number(ctx: RuleContext, key: C | E) -> float | None:
    """Return a numeric input as float; None when missing, bool, non-numeric or NaN."""
    value = ctx.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value):
        return None
    return float(value)


def _numbers(ctx: RuleContext, key: C | E) -> tuple[float, ...] | None:
    """Return a non-empty sequence of numbers (e.g. sleep history); None otherwise."""
    value = ctx.get(key)
    if not isinstance(value, (tuple, list)) or not value:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) for v in value):
        return None
    return tuple(float(v) for v in value)


def _flag(ctx: RuleContext, key: C | E) -> bool | None:
    """Return a yes/no input; None when missing or not a real bool."""
    value = ctx.get(key)
    return value if isinstance(value, bool) else None


def _sex(ctx: RuleContext) -> Sex | None:
    """Accept Sex or 'M'/'F' strings (case-insensitive); anything else counts as missing."""
    value = ctx.get(E.SEX)
    if isinstance(value, Sex):
        return value
    if isinstance(value, str):
        return {"M": Sex.M, "F": Sex.F}.get(value.strip().upper())
    return None


def _test(op: Callable[[float, float], bool], value: float | None, limit: float) -> _Part:
    """Compare value with limit; None when the value is missing."""
    return None if value is None else op(value, limit)


def _fire(condition: _Part, status: Status) -> Status:
    """UNKNOWN for an undecidable condition, `status` when it holds, OK otherwise."""
    if condition is None:
        return Status.UNKNOWN
    return status if condition else Status.OK


def _any_fires(parts: tuple[Status, ...]) -> Status:
    """Highest firing part; OK only if every part is decidable and OK; else UNKNOWN."""
    fired = max(parts, default=Status.UNKNOWN)
    if fired >= Status.WATCH:
        return fired
    if parts and all(part is Status.OK for part in parts):
        return Status.OK
    return Status.UNKNOWN


def _single(
    ctx: RuleContext, key: C | E, op: Callable[[float, float], bool], limit: float, status: Status
) -> Status:
    return _fire(_test(op, _number(ctx, key), limit), status)


def _band(ctx: RuleContext, key: C | E, low: float, high: float, status: Status) -> Status:
    """`status` when low <= value < high."""
    value = _number(ctx, key)
    return _fire(None if value is None else low <= value < high, status)


def _by_sex(
    value: float | None,
    sex: Sex | None,
    table: Mapping[Sex, float],
    op: Callable[[float, float], bool],
) -> _Part:
    """Test value against the sex-specific limit. Sex unknown: decided only if both limits agree."""
    if value is None:
        return None
    if sex is not None:
        return op(value, table[sex])
    low_result = op(value, min(table.values()))
    high_result = op(value, max(table.values()))
    return low_result if low_result == high_result else None


def _drop_percent(baseline: float | None, now: float | None) -> float | None:
    """Percentage drop from a positive baseline; None when not computable."""
    if baseline is None or now is None or baseline <= 0:
        return None
    return (baseline - now) / baseline * 100


def _bp_crisis(ctx: RuleContext) -> _Part:
    """True when SBP or DBP is in crisis; False only when both are known and not in crisis."""
    sbp = _number(ctx, C.SYSTOLIC_BLOOD_PRESSURE)
    dbp = _number(ctx, C.DIASTOLIC_BLOOD_PRESSURE)
    parts = (_test(operator.gt, sbp, BP_CRISIS_SYSTOLIC), _test(operator.gt, dbp, BP_CRISIS_DIASTOLIC))
    if any(part is True for part in parts):
        return True
    return False if all(part is False for part in parts) else None


def _vo2_percent(ctx: RuleContext) -> float | None:
    now = _number(ctx, E.VO2_MAX)
    preflight = _number(ctx, E.VO2_MAX_PREFLIGHT)
    if now is None or preflight is None or preflight <= 0:
        return None
    return vo2_percent_of_preflight(now, preflight)


def _delta(ctx: RuleContext, standing: E, supine: E) -> float | None:
    after, before = _number(ctx, standing), _number(ctx, supine)
    return None if after is None or before is None else after - before


def _whtr(ctx: RuleContext) -> float | None:
    waist, height = _number(ctx, E.WAIST_CIRCUMFERENCE_CM), _number(ctx, C.HEIGHT)
    if waist is None or height is None or waist <= 0 or height <= 0:
        return None
    return waist_to_height_ratio(waist, height)


def _sleep_deficit_hours(hours: float, age: float | None) -> float:
    """Deficit versus the recommendation; without a valid adult age the constant is used."""
    if age is None or age < MIN_ADULT_AGE:
        return RECOMMENDED_SLEEP_MIN_HOURS - hours
    return sleep_deficit(hours, age)


def _sleep_debt_exceeded(ctx: RuleContext) -> _Part:
    history = _numbers(ctx, E.SLEEP_HOURS_HISTORY)
    if history is None:
        return None
    age = _number(ctx, C.AGE)
    if age is None or age < MIN_ADULT_AGE:
        return sum(RECOMMENDED_SLEEP_MIN_HOURS - hours for hours in history) > SLEEP_DEBT_MAX_HOURS
    return cumulative_sleep_debt(history, age) > SLEEP_DEBT_MAX_HOURS


def _pss10_total(ctx: RuleContext) -> int | None:
    """PSS-10 score, or None when the answers are missing or not 10 answers of 0-4."""
    answers = _numbers(ctx, E.PSS10_ANSWERS)
    if answers is None or len(answers) != 10 or any(a != int(a) or not 0 <= a <= 4 for a in answers):
        return None
    return pss10_score([int(a) for a in answers])


def _radiation_percent(ctx: RuleContext) -> tuple[float, bool] | None:
    """(% of career limit, is_lower_bound). Without prior dose the mission dose is a lower bound."""
    mission = _number(ctx, C.MISSION_RADIATION_LEVEL)
    if mission is None:
        return None
    prior = _number(ctx, E.PRIOR_CAREER_DOSE_MSV)
    doses = [mission] if prior is None else [prior, mission]
    return radiation_limit_percent(career_radiation_dose(doses)), prior is None


def _radiation_status(ctx: RuleContext, threshold: float, status: Status) -> Status:
    result = _radiation_percent(ctx)
    if result is None:
        return Status.UNKNOWN
    percent, is_lower_bound = result
    if percent >= threshold:
        return status
    return Status.UNKNOWN if is_lower_bound else Status.OK


# --- Assessors (one per rule) ------------------------------------------------------------
def _assess_cv1(ctx: RuleContext) -> Status:
    crisis = _bp_crisis(ctx)
    if crisis is None:
        return Status.UNKNOWN
    if not crisis:
        return Status.OK
    return _fire(_flag(ctx, E.HYPERTENSIVE_SYMPTOMS), Status.URGENT)


def _assess_cv2(ctx: RuleContext) -> Status:
    crisis = _bp_crisis(ctx)
    if crisis is None:
        return Status.UNKNOWN
    if not crisis:
        return Status.OK
    return Status.OK if _flag(ctx, E.HYPERTENSIVE_SYMPTOMS) is True else Status.ACTION


def _assess_cv3(ctx: RuleContext) -> Status:
    sbp = _number(ctx, C.SYSTOLIC_BLOOD_PRESSURE)
    dbp = _number(ctx, C.DIASTOLIC_BLOOD_PRESSURE)
    return _any_fires((
        _fire(_test(operator.ge, sbp, BP_HIGH_SYSTOLIC), Status.WATCH),
        _fire(_test(operator.ge, dbp, BP_HIGH_DIASTOLIC), Status.WATCH),
    ))


def _assess_cv4(ctx: RuleContext) -> Status:
    sbp = _number(ctx, C.SYSTOLIC_BLOOD_PRESSURE)
    dbp = _number(ctx, C.DIASTOLIC_BLOOD_PRESSURE)
    return _any_fires((
        _fire(_test(operator.lt, sbp, BP_LOW_SYSTOLIC), Status.WATCH),
        _fire(_test(operator.lt, dbp, BP_LOW_DIASTOLIC), Status.WATCH),
    ))


def _assess_cv5(ctx: RuleContext) -> Status:
    rate = _number(ctx, C.AVERAGE_HEART_RATE)
    return _any_fires((
        _fire(_test(operator.lt, rate, RESTING_HR_LOW), Status.WATCH),
        _fire(_test(operator.gt, rate, RESTING_HR_HIGH), Status.WATCH),
    ))


def _assess_cv6(ctx: RuleContext) -> Status:
    symptoms = _flag(ctx, E.ORTHOSTATIC_SYMPTOMS)
    if symptoms is None:
        return Status.UNKNOWN
    if not symptoms:
        return Status.OK
    d_sbp = _delta(ctx, E.SYSTOLIC_STANDING, E.SYSTOLIC_SUPINE)
    d_hr = _delta(ctx, E.HEART_RATE_STANDING, E.HEART_RATE_SUPINE)
    return _any_fires((
        _fire(_test(operator.le, d_sbp, -ORTHOSTATIC_SBP_DROP_MMHG), Status.ACTION),
        _fire(_test(operator.ge, d_hr, ORTHOSTATIC_HR_RISE_BPM), Status.ACTION),
    ))


def _assess_cv7(ctx: RuleContext) -> Status:
    percent = _vo2_percent(ctx)
    return _fire(_test(operator.lt, percent, VO2_MIN_PERCENT), Status.ACTION)


def _assess_cv8(ctx: RuleContext) -> Status:
    percent = _vo2_percent(ctx)
    in_band = None if percent is None else VO2_MIN_PERCENT <= percent < VO2_WATCH_PERCENT
    return _fire(in_band, Status.WATCH)


def _assess_bl1(ctx: RuleContext) -> Status:
    hemoglobin = _number(ctx, E.HEMOGLOBIN_G_DL)
    lower_limit = _number(ctx, E.HEMOGLOBIN_LAB_LOWER_LIMIT_G_DL)
    if hemoglobin is None or lower_limit is None:
        return Status.UNKNOWN
    return _fire(hemoglobin < lower_limit, Status.WATCH)


def _assess_mt1(ctx: RuleContext) -> Status:
    return _single(ctx, C.BLOOD_GLUCOSE, operator.lt, GLUCOSE_LEVEL2_HYPO, Status.URGENT)


def _assess_mt2(ctx: RuleContext) -> Status:
    return _band(ctx, C.BLOOD_GLUCOSE, GLUCOSE_LEVEL2_HYPO, GLUCOSE_LEVEL1_HYPO, Status.ACTION)


def _assess_mt3(ctx: RuleContext) -> Status:
    return _band(ctx, C.BLOOD_GLUCOSE, GLUCOSE_PREDIABETES, GLUCOSE_DIABETES, Status.WATCH)


def _assess_mt4(ctx: RuleContext) -> Status:
    return _single(ctx, C.BLOOD_GLUCOSE, operator.ge, GLUCOSE_DIABETES, Status.ACTION)


def _assess_mt5(ctx: RuleContext) -> Status:
    hba1c = _number(ctx, E.HBA1C_PERCENT)
    if hba1c is None:
        return Status.UNKNOWN
    if hba1c >= HBA1C_DIABETES:
        return Status.ACTION
    return Status.WATCH if hba1c >= HBA1C_PREDIABETES else Status.OK


def _assess_mt6(ctx: RuleContext) -> Status:
    return _single(ctx, E.ENERGY_DEFICIT_DAYS, operator.ge, ENERGY_DEFICIT_MIN_DAYS, Status.WATCH)


def _assess_mt7(ctx: RuleContext) -> Status:
    bmi = _number(ctx, C.BODY_MASS_INDEX)
    return _any_fires((
        _fire(_test(operator.lt, bmi, BMI_UNDERWEIGHT), Status.WATCH),
        _fire(_test(operator.ge, bmi, BMI_OBESE), Status.WATCH),
    ))


def _assess_mt8(ctx: RuleContext) -> Status:
    fat = _number(ctx, C.BODY_FAT_PERCENTAGE)
    return _fire(_by_sex(fat, _sex(ctx), ESSENTIAL_FAT_MAX_PERCENT, operator.lt), Status.ACTION)


def _assess_mt9(ctx: RuleContext) -> Status:
    fat = _number(ctx, C.BODY_FAT_PERCENTAGE)
    fat_part = _fire(_by_sex(fat, _sex(ctx), HIGH_FAT_PERCENT, operator.ge), Status.WATCH)
    whtr_part = _fire(_test(operator.ge, _whtr(ctx), WHTR_HIGH), Status.WATCH)
    return _any_fires((fat_part, whtr_part))


def _assess_ms1(ctx: RuleContext) -> Status:
    drop = _drop_percent(
        _number(ctx, E.MUSCLE_MASS_PERCENTAGE_PREFLIGHT), _number(ctx, C.MUSCLE_MASS_PERCENTAGE)
    )
    return _fire(_test(operator.gt, drop, MUSCLE_DROP_PERCENT), Status.WATCH)


def _assess_ms2(ctx: RuleContext) -> Status:
    grip = _number(ctx, E.GRIP_STRENGTH_KG)
    return _fire(_by_sex(grip, _sex(ctx), GRIP_STRENGTH_MIN_KG, operator.lt), Status.ACTION)


def _assess_bn1(ctx: RuleContext) -> Status:
    preflight = _number(ctx, E.BONE_DENSITY_PREFLIGHT)
    now = _number(ctx, C.BONE_DENSITY_CALCIUM)
    months = _number(ctx, E.MONTHS_IN_FLIGHT)
    if preflight is None or now is None or months is None or preflight <= 0 or months <= 0:
        return Status.UNKNOWN
    rate = bone_loss_rate(preflight, now, months)
    return _fire(rate > BONE_LOSS_RATE_MAX, Status.WATCH)


def _assess_bn2(ctx: RuleContext) -> Status:
    value = _number(ctx, E.T_SCORE)
    in_band = None if value is None else T_SCORE_OSTEOPOROSIS < value < T_SCORE_NORMAL_MIN
    return _fire(in_band, Status.WATCH)


def _assess_bn3(ctx: RuleContext) -> Status:
    return _single(ctx, E.T_SCORE, operator.le, T_SCORE_OSTEOPOROSIS, Status.ACTION)


def _assess_bn4(ctx: RuleContext) -> Status:
    return _single(ctx, E.VITAMIN_D_NG_ML, operator.lt, VITAMIN_D_LOW_NG_ML, Status.WATCH)


def _assess_kd1(ctx: RuleContext) -> Status:
    if ctx.phase is MissionPhase.RETURN:
        return Status.WATCH
    if ctx.phase in (MissionPhase.ADAPTATION, MissionPhase.LONG_DURATION):
        return Status.OK
    return Status.UNKNOWN


def _assess_sl1(ctx: RuleContext) -> Status:
    hours = _number(ctx, C.SLEEP_HOURS)
    if hours is None:
        return Status.UNKNOWN
    deficit = _sleep_deficit_hours(hours, _number(ctx, C.AGE))
    return _fire(deficit > 0, Status.WATCH)


def _assess_sl2(ctx: RuleContext) -> Status:
    hours = _number(ctx, C.SLEEP_HOURS)
    short = _fire(_test(operator.le, hours, SLEEP_SHORT_HOURS), Status.ACTION)
    debt = _fire(_sleep_debt_exceeded(ctx), Status.ACTION)
    if max(short, debt) >= Status.WATCH:
        return Status.ACTION
    return Status.OK if hours is not None else Status.UNKNOWN


def _assess_sl3(ctx: RuleContext) -> Status:
    hours = _number(ctx, C.SLEEP_HOURS)
    in_bed = _number(ctx, E.TIME_IN_BED_HOURS)
    efficiency: float | None = None
    if hours is not None and in_bed is not None and 0 < in_bed and hours <= in_bed:
        efficiency = sleep_efficiency(hours, in_bed)
    return _any_fires((
        _fire(_test(operator.lt, efficiency, SLEEP_EFFICIENCY_MIN), Status.WATCH),
        _fire(
            _test(operator.gt, _number(ctx, E.SLEEP_LATENCY_MIN), SLEEP_LATENCY_MAX_MIN), Status.WATCH
        ),
    ))


def _assess_cg1(ctx: RuleContext) -> Status:
    lapses = _number(ctx, E.PVT_LAPSES)
    baseline = _number(ctx, E.PVT_LAPSES_BASELINE)
    if lapses is None or baseline is None:
        return Status.UNKNOWN
    increase = lapses - baseline
    if increase >= PVT_LAPSE_INCREASE_ACTION:
        return Status.ACTION
    return Status.WATCH if increase >= PVT_LAPSE_INCREASE_WATCH else Status.OK


def _assess_ps1(ctx: RuleContext) -> Status:
    return _band(ctx, C.STRESS_LEVEL, STRESS_MODERATE_MIN, STRESS_HIGH_MIN, Status.WATCH)


def _assess_ps2(ctx: RuleContext) -> Status:
    stress = _number(ctx, C.STRESS_LEVEL)
    stress_part = _fire(_test(operator.ge, stress, STRESS_HIGH_MIN), Status.ACTION)
    score = _pss10_total(ctx)
    pss_part = _fire(None if score is None else score >= PSS10_HIGH_MIN, Status.ACTION)
    if max(stress_part, pss_part) >= Status.WATCH:
        return Status.ACTION
    return Status.OK if stress is not None else Status.UNKNOWN


def _assess_ps3(ctx: RuleContext) -> Status:
    drop = _drop_percent(_number(ctx, E.HRV_RMSSD_BASELINE_MS), _number(ctx, E.HRV_RMSSD_MS))
    return _fire(_test(operator.ge, drop, HRV_DROP_PERCENT), Status.WATCH)


def _assess_rd1(ctx: RuleContext) -> Status:
    return _radiation_status(ctx, RADIATION_WATCH_PERCENT, Status.WATCH)


def _assess_rd2(ctx: RuleContext) -> Status:
    return _radiation_status(ctx, RADIATION_ACTION_PERCENT, Status.ACTION)


def _assess_rd3(ctx: RuleContext) -> Status:
    return _radiation_status(ctx, RADIATION_URGENT_PERCENT, Status.URGENT)


def _assess_ey1(ctx: RuleContext) -> Status:
    return _fire(_flag(ctx, E.SANS_NEW_FINDINGS), Status.ACTION)


def _assess_ey2(ctx: RuleContext) -> Status:
    return _fire(_flag(ctx, E.SANS_GRADE_WORSENED), Status.URGENT)


# --- Rules table (spec order) ------------------------------------------------------------
_HEART = BodySystem.HEART_VESSELS
_BRAIN = BodySystem.BRAIN
_MUSCLES = BodySystem.MUSCLES
_BONES = BodySystem.BONES
_METAB = BodySystem.METABOLISM
_SLEEP = BodySystem.SLEEP
_P = MissionPhase
_PH_AR = (_P.ADAPTATION, _P.RETURN)
_PH_DR = (_P.LONG_DURATION, _P.RETURN)
_PH_D = (_P.LONG_DURATION,)
_PH_R = (_P.RETURN,)
_BP_KEYS = (C.SYSTOLIC_BLOOD_PRESSURE, C.DIASTOLIC_BLOOD_PRESSURE)
_BP_CRISIS_TEXT = f"SBP > {BP_CRISIS_SYSTOLIC} or DBP > {BP_CRISIS_DIASTOLIC}"
_VO2_KEYS = (E.VO2_MAX, E.VO2_MAX_PREFLIGHT)
_GLUCOSE = (C.BLOOD_GLUCOSE,)
_T_SCORE = (E.T_SCORE,)
_RADIATION_KEYS = (C.MISSION_RADIATION_LEVEL, E.PRIOR_CAREER_DOSE_MSV)
_RADIATION_NOTE = f"% of career limit ({CAREER_RADIATION_LIMIT_MSV:g} mSv)"

RULES: tuple[Rule, ...] = (
    Rule("CV-1", "Blood pressure", f"{_BP_CRISIS_TEXT} with symptoms", Status.URGENT,
         (_HEART, _BRAIN), ("Emergency medical response", ACTION_CONTACT_FLIGHT_SURGEON),
         "[S14, S15]", (*_BP_KEYS, E.HYPERTENSIVE_SYMPTOMS), _PH_AR, _assess_cv1),
    Rule("CV-2", "Blood pressure", f"{_BP_CRISIS_TEXT}, no symptoms", Status.ACTION,
         (_HEART,), ("Rest and recheck", "Prompt contact with the flight surgeon"),
         "[S14, S15]", (*_BP_KEYS, E.HYPERTENSIVE_SYMPTOMS), _PH_AR, _assess_cv2),
    Rule("CV-3", "Blood pressure", f"SBP >= {BP_HIGH_SYSTOLIC} or DBP >= {BP_HIGH_DIASTOLIC}",
         Status.WATCH, (_HEART,), (ACTION_RECHECK_AT_REST, "Report BP trend to the medical team"),
         "calc 6", _BP_KEYS, _PH_AR, _assess_cv3),
    Rule("CV-4", "Blood pressure", f"SBP < {BP_LOW_SYSTOLIC} or DBP < {BP_LOW_DIASTOLIC}",
         Status.WATCH, (_HEART, BodySystem.KIDNEYS_FLUIDS),
         (ACTION_RECHECK_AT_REST, "If near return, check the orthostatic test (CV-6)"),
         "calc 6", _BP_KEYS, _PH_AR, _assess_cv4),
    Rule("CV-5", "Resting HR", f"< {RESTING_HR_LOW} or > {RESTING_HR_HIGH} bpm at rest",
         Status.WATCH, (_HEART,), (ACTION_RECHECK_AT_REST, "Medical review if persistent"),
         "calc 7", (C.AVERAGE_HEART_RATE,), _PH_AR, _assess_cv5),
    Rule("CV-6", "Orthostatic test",
         f"symptoms + SBP drop >= {ORTHOSTATIC_SBP_DROP_MMHG} mmHg or HR rise >= "
         f"{ORTHOSTATIC_HR_RISE_BPM} bpm on standing", Status.ACTION, (_HEART, _BRAIN),
         ("Fluid and salt loading before reentry", ACTION_MEDICAL_REVIEW),
         "[S1, S3]; thresholds [unverified/design]",
         (E.ORTHOSTATIC_SYMPTOMS, E.SYSTOLIC_SUPINE, E.SYSTOLIC_STANDING,
          E.HEART_RATE_SUPINE, E.HEART_RATE_STANDING), _PH_R, _assess_cv6),
    Rule("CV-7", "VO2max", f"< {VO2_MIN_PERCENT:g}% of preflight", Status.ACTION,
         (_HEART, _MUSCLES), (ACTION_AEROBIC_EXERCISE,),
         "[S8, S9], NASA-STD-3001 snippet", _VO2_KEYS, _PH_DR, _assess_cv7),
    Rule("CV-8", "VO2max", f"{VO2_MIN_PERCENT:g}-{VO2_WATCH_PERCENT}% of preflight", Status.WATCH,
         (_HEART,), (ACTION_AEROBIC_EXERCISE, "Recheck VO2max sooner"),
         "[design]", _VO2_KEYS, _PH_DR, _assess_cv8),
    Rule("BL-1", "Hemoglobin", "below the lab lower limit", Status.WATCH, (BodySystem.BLOOD,),
         (ACTION_MEDICAL_FOLLOW_UP, "Recheck after return (recovery 30 days to 3-4 months)"),
         "[S11, S12], thresholds open",
         (E.HEMOGLOBIN_G_DL, E.HEMOGLOBIN_LAB_LOWER_LIMIT_G_DL), ALL_PHASES, _assess_bl1),
    Rule("MT-1", "Glucose", f"< {GLUCOSE_LEVEL2_HYPO} mg/dL", Status.URGENT, (_METAB, _BRAIN),
         ("Treat immediately per medical protocol", ACTION_CONTACT_FLIGHT_SURGEON),
         "[S16]", _GLUCOSE, ALL_PHASES, _assess_mt1),
    Rule("MT-2", "Glucose", f"{GLUCOSE_LEVEL2_HYPO}-{GLUCOSE_LEVEL1_HYPO - 1} mg/dL (< {GLUCOSE_LEVEL1_HYPO})",
         Status.ACTION, (_METAB, _BRAIN), ("Treat per medical protocol", "Recheck glucose"),
         "[S16]", _GLUCOSE, ALL_PHASES, _assess_mt2),
    Rule("MT-3", "Glucose (fasting)", f"{GLUCOSE_PREDIABETES}-{GLUCOSE_DIABETES - 1} mg/dL",
         Status.WATCH, (_METAB,), (ACTION_NUTRITION_REVIEW, "Recheck fasting glucose"),
         "calc 8", _GLUCOSE, ALL_PHASES, _assess_mt3),
    Rule("MT-4", "Glucose (fasting)", f">= {GLUCOSE_DIABETES} mg/dL", Status.ACTION, (_METAB,),
         (ACTION_MEDICAL_FOLLOW_UP,), "calc 8", _GLUCOSE, ALL_PHASES, _assess_mt4),
    Rule("MT-5", "HbA1c", f"{HBA1C_PREDIABETES}-{HBA1C_DIABETES - 0.1:.1f}% (WATCH) / >= {HBA1C_DIABETES}% (ACTION)",
         Status.ACTION, (_METAB,), (ACTION_MEDICAL_FOLLOW_UP, ACTION_NUTRITION_REVIEW),
         "[unverified]", (E.HBA1C_PERCENT,), ALL_PHASES, _assess_mt5),
    Rule("MT-6", "Energy balance", f"intake < TDEE for >= {ENERGY_DEFICIT_MIN_DAYS} days",
         Status.WATCH, (_METAB, _MUSCLES), ("Nutrition plan to close the energy deficit",),
         "[S32]; day count [design]", (E.ENERGY_DEFICIT_DAYS,), _PH_D, _assess_mt6),
    Rule("MT-7", "BMI", f"< {BMI_UNDERWEIGHT} or >= {BMI_OBESE}", Status.WATCH, (_METAB, _MUSCLES),
         (ACTION_NUTRITION_REVIEW, ACTION_EXERCISE_REVIEW), "calc 5",
         (C.BODY_MASS_INDEX,), _PH_D, _assess_mt7),
    Rule("MT-8", "Body fat %",
         f"below essential fat (men < {ESSENTIAL_FAT_MAX_PERCENT[Sex.M]:g}, "
         f"women < {ESSENTIAL_FAT_MAX_PERCENT[Sex.F]:g})", Status.ACTION, (_METAB,),
         (ACTION_NUTRITION_REVIEW, ACTION_MEDICAL_FOLLOW_UP), "[S23]; limits [design]",
         (C.BODY_FAT_PERCENTAGE, E.SEX), _PH_D, _assess_mt8),
    Rule("MT-9", "Body fat % / WHtR",
         f"men >= {HIGH_FAT_PERCENT[Sex.M]:g}, women >= {HIGH_FAT_PERCENT[Sex.F]:g} / WHtR >= {WHTR_HIGH}",
         Status.WATCH, (_METAB, _HEART), (ACTION_NUTRITION_REVIEW, ACTION_EXERCISE_REVIEW),
         "[S23, S25]", (C.BODY_FAT_PERCENTAGE, E.SEX, E.WAIST_CIRCUMFERENCE_CM, C.HEIGHT),
         _PH_D, _assess_mt9),
    Rule("MS-1", "Muscle %", f"drop from preflight > {MUSCLE_DROP_PERCENT}%", Status.WATCH,
         (_MUSCLES,), (ACTION_RESISTANCE_EXERCISE,), "[S31]; X [design]",
         (C.MUSCLE_MASS_PERCENTAGE, E.MUSCLE_MASS_PERCENTAGE_PREFLIGHT), _PH_DR, _assess_ms1),
    Rule("MS-2", "Grip strength",
         f"men < {GRIP_STRENGTH_MIN_KG[Sex.M]:g} kg, women < {GRIP_STRENGTH_MIN_KG[Sex.F]:g} kg",
         Status.ACTION, (_MUSCLES,), (ACTION_RESISTANCE_EXERCISE, ACTION_MEDICAL_REVIEW),
         "[S24, S31]", (E.GRIP_STRENGTH_KG, E.SEX), _PH_DR, _assess_ms2),
    Rule("BN-1", "Bone loss rate", f"> {BONE_LOSS_RATE_MAX}%/month", Status.WATCH, (_BONES,),
         (ACTION_RESISTANCE_EXERCISE, "In-flight deadlifting is linked to better recovery"),
         "[S26, S28]; cutoff [design]",
         (C.BONE_DENSITY_CALCIUM, E.BONE_DENSITY_PREFLIGHT, E.MONTHS_IN_FLIGHT), _PH_DR, _assess_bn1),
    Rule("BN-2", "T-score", f"below {T_SCORE_NORMAL_MIN} and above {T_SCORE_OSTEOPOROSIS}",
         Status.WATCH, (_BONES,), (ACTION_RESISTANCE_EXERCISE, ACTION_NUTRITION_REVIEW),
         "[S22]", _T_SCORE, _PH_DR, _assess_bn2),
    Rule("BN-3", "T-score", f"<= {T_SCORE_OSTEOPOROSIS}", Status.ACTION, (_BONES,),
         ("Medical evaluation; any drug only under medical supervision",),
         "[S22]", _T_SCORE, _PH_DR, _assess_bn3),
    Rule("BN-4", "Vitamin D", f"< {VITAMIN_D_LOW_NG_ML} ng/mL", Status.WATCH, (_BONES,),
         ("Supplementation as decided by the medical team",), "[unverified], [S32]",
         (E.VITAMIN_D_NG_ML,), _PH_D, _assess_bn4),
    Rule("KD-1", "Urine chemistry / return phase", "after return, first year", Status.WATCH,
         (BodySystem.KIDNEYS_FLUIDS, _BONES), ("Monitor urine chemistry for stone risk",),
         "[S29, S30]", (E.MISSION_PHASE,), _PH_R, _assess_kd1),
    Rule("SL-1", "Sleep hours", f"< recommended for age ({RECOMMENDED_SLEEP_MIN_HOURS:g} h)",
         Status.WATCH, (_SLEEP, _BRAIN), (ACTION_SLEEP_SCHEDULE,), "[S37, S42, S44]",
         (C.SLEEP_HOURS, C.AGE), ALL_PHASES, _assess_sl1),
    Rule("SL-2", "Sleep hours",
         f"<= {SLEEP_SHORT_HOURS} h, or sleep debt over {SLEEP_DEBT_MAX_HOURS} h",
         Status.ACTION, (_SLEEP, _BRAIN),
         (ACTION_SLEEP_SCHEDULE, ACTION_WORKLOAD_REVIEW, "Medication only after behavioural options"),
         "[S40, S43]; Y [design]", (C.SLEEP_HOURS, E.SLEEP_HOURS_HISTORY, C.AGE),
         ALL_PHASES, _assess_sl2),
    Rule("SL-3", "Sleep efficiency / latency",
         f"efficiency < {SLEEP_EFFICIENCY_MIN}% or latency > {SLEEP_LATENCY_MAX_MIN} min",
         Status.WATCH, (_SLEEP,), (ACTION_SLEEP_HYGIENE,), "[unverified]",
         (C.SLEEP_HOURS, E.TIME_IN_BED_HOURS, E.SLEEP_LATENCY_MIN), ALL_PHASES, _assess_sl3),
    Rule("CG-1", "PVT lapses",
         f"increase vs baseline >= {PVT_LAPSE_INCREASE_WATCH} (ACTION if >= {PVT_LAPSE_INCREASE_ACTION})",
         Status.ACTION, (_BRAIN, _SLEEP), ("Review sleep and workload",),
         "[S40, S47]; size [design]", (E.PVT_LAPSES, E.PVT_LAPSES_BASELINE), _PH_D, _assess_cg1),
    Rule("PS-1", "Stress 1-10", f"{STRESS_MODERATE_MIN}-{STRESS_HIGH_MIN - 1}", Status.WATCH,
         (_BRAIN,), ("Stress management; track trend",), "[design]",
         (C.STRESS_LEVEL,), _PH_D, _assess_ps1),
    Rule("PS-2", "Stress 1-10 / PSS-10", f">= {STRESS_HIGH_MIN} / PSS-10 >= {PSS10_HIGH_MIN}",
         Status.ACTION, (_BRAIN, _SLEEP), ("Psychological support",), "[design], [S45, S46]",
         (C.STRESS_LEVEL, E.PSS10_ANSWERS), _PH_D, _assess_ps2),
    Rule("PS-3", "HRV", f"RMSSD drop >= {HRV_DROP_PERCENT}% vs baseline", Status.WATCH,
         (_HEART, _BRAIN), ("Check sleep and stress rules",), "[design]",
         (E.HRV_RMSSD_MS, E.HRV_RMSSD_BASELINE_MS), ALL_PHASES, _assess_ps3),
    Rule("RD-1", "Radiation", f">= {RADIATION_WATCH_PERCENT} {_RADIATION_NOTE}",
         Status.WATCH, (BodySystem.BLOOD, BodySystem.IMMUNE),
         ("ALARA: minimise further exposure",), "[S34]; 50% [design]",
         _RADIATION_KEYS, _PH_D, _assess_rd1),
    Rule("RD-2", "Radiation", f">= {RADIATION_ACTION_PERCENT} {_RADIATION_NOTE}", Status.ACTION,
         SYSTEM_ORDER, ("Mission planning review with the medical team",), "80% [design]",
         _RADIATION_KEYS, _PH_D, _assess_rd2),
    Rule("RD-3", "Radiation", f">= {RADIATION_URGENT_PERCENT} {_RADIATION_NOTE}", Status.URGENT,
         SYSTEM_ORDER,
         ("Limit reached: no further exposure without a medical/program decision",
          "Shielding / storm shelter during solar events"),
         "[S33, S34]", _RADIATION_KEYS, _PH_D, _assess_rd3),
    Rule("EY-1", "SANS findings", "any new disc edema, folds or globe flattening", Status.ACTION,
         (BodySystem.EYES,), ("Ophthalmic exam follow-up",), "[S48, S49]",
         (E.SANS_NEW_FINDINGS,), _PH_DR, _assess_ey1),
    Rule("EY-2", "SANS findings", "grade worsens between exams", Status.URGENT,
         (BodySystem.EYES,), ("Immediate ophthalmic / medical review", ACTION_CONTACT_FLIGHT_SURGEON),
         "[design]", (E.SANS_GRADE_WORSENED,), _PH_DR, _assess_ey2),
)

_RULES_BY_ID: Mapping[str, Rule] = MappingProxyType({rule.id: rule for rule in RULES})


def rule_by_id(rule_id: str) -> Rule:
    """Return the rule with this id; KeyError for an unknown id."""
    return _RULES_BY_ID[rule_id]
