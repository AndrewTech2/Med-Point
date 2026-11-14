"""Tests for recommendation_types.py, recommendation_rules.py and recommendations.py."""

import copy
import dataclasses
import math

import pytest

import recommendation_rules as rr
import recommendations as rec
from calculations import Sex
from Caracteristici import CHARACTERISTIC_DEFINITIONS, Characteristic as C
from recommendation_rules import RULES, rule_by_id
from recommendation_types import (
    SYSTEM_ORDER,
    BodySystem,
    ExtraInput as E,
    MissionPhase,
    Rule,
    Status,
    make_context,
)

OK, WATCH, ACTION, URGENT, UNKNOWN = (
    Status.OK, Status.WATCH, Status.ACTION, Status.URGENT, Status.UNKNOWN,
)
SBP, DBP, HR = C.SYSTOLIC_BLOOD_PRESSURE, C.DIASTOLIC_BLOOD_PRESSURE, C.AVERAGE_HEART_RATE
HS, OS = E.HYPERTENSIVE_SYMPTOMS, E.ORTHOSTATIC_SYMPTOMS
SEX = E.SEX
M, F = Sex.M, Sex.F
PHASES = MissionPhase


def run(rule_id: str, values: dict | None = None, phase: MissionPhase = PHASES.UNKNOWN) -> Status:
    return rule_by_id(rule_id).assess(make_context(values or {}, phase))


def case(rule_id: str, values: dict, expected: Status, phase: MissionPhase = PHASES.UNKNOWN):
    shown = ",".join(f"{getattr(k, 'name', k)}={v}" for k, v in values.items())
    return pytest.param(rule_id, values, expected, phase, id=f"{rule_id}[{shown}]->{expected.name}")


def fake_rule(rule_id, status=WATCH, systems=(BodySystem.BRAIN,), actions=None, phases=(),
              inputs=(), assess=None) -> Rule:
    return Rule(rule_id, "var", "cond", status, tuple(systems), tuple(actions or (f"act-{rule_id}",)),
                f"[{rule_id}]", tuple(inputs), tuple(phases), assess or (lambda ctx, s=status: s))


def result(rule: Rule, status: Status) -> rec.RuleResult:
    return rec.RuleResult(rule=rule, status=status)


def by_id(assessment: rec.Assessment) -> dict[str, Status]:
    return {r.rule.id: r.status for r in assessment.results}


def system_map(assessment: rec.Assessment) -> dict[BodySystem, rec.SystemStatus]:
    return {s.system: s for s in assessment.systems}


HEALTHY = {
    C.AGE: 35, C.BODY_WEIGHT: 75, C.HEIGHT: 180, C.BODY_MASS_INDEX: 23, HR: 70, SBP: 115, DBP: 75,
    C.MUSCLE_MASS_PERCENTAGE: 40, C.BODY_FAT_PERCENTAGE: 18, C.STRESS_LEVEL: 2,
    C.MISSION_RADIATION_LEVEL: 10, C.BONE_DENSITY_CALCIUM: 1.2, C.BLOOD_GLUCOSE: 85, C.SLEEP_HOURS: 8,
}

# ---------------------------------------------------------------- threshold tables
GLUCOSE_TABLE = [  # glucose -> (MT-1, MT-2, MT-3, MT-4)
    (53.9, (URGENT, OK, OK, OK)), (54, (OK, ACTION, OK, OK)), (69.9, (OK, ACTION, OK, OK)),
    (70, (OK, OK, OK, OK)), (99.9, (OK, OK, OK, OK)), (100, (OK, OK, WATCH, OK)),
    (125.9, (OK, OK, WATCH, OK)), (126, (OK, OK, OK, ACTION)),
]
VO2_TABLE = [(79.9, (ACTION, OK)), (80, (OK, WATCH)), (89.9, (OK, WATCH)), (90, (OK, OK))]
# career dose in mSv (mission 100 + prior) -> (RD-1, RD-2, RD-3); 600 mSv = 100 %
RADIATION_TABLE = [
    (299.4, (OK, OK, OK)), (300, (WATCH, OK, OK)), (479.4, (WATCH, OK, OK)),
    (480, (WATCH, ACTION, OK)), (599.4, (WATCH, ACTION, OK)), (600, (WATCH, ACTION, URGENT)),
]
THRESHOLD_CASES = [
    # CV-1 / CV-2
    *[case("CV-1", v, e) for v, e in [
        ({SBP: 180, DBP: 100, HS: True}, OK), ({SBP: 181, DBP: 100, HS: True}, URGENT),
        ({SBP: 150, DBP: 120, HS: True}, OK), ({SBP: 150, DBP: 121, HS: True}, URGENT),
        ({SBP: 181, DBP: 100, HS: False}, OK), ({SBP: 181, DBP: 100}, UNKNOWN),
        ({SBP: 181, HS: True}, URGENT), ({SBP: 150, DBP: 100}, OK), ({SBP: 150}, UNKNOWN), ({}, UNKNOWN),
    ]],
    *[case("CV-2", v, e) for v, e in [
        ({SBP: 181, DBP: 100, HS: True}, OK), ({SBP: 181, DBP: 100, HS: False}, ACTION),
        ({SBP: 181, DBP: 100}, ACTION), ({SBP: 180, DBP: 120}, OK), ({SBP: 150, DBP: 121}, ACTION),
        ({DBP: 100}, UNKNOWN),
    ]],
    # CV-3 .. CV-5
    *[case("CV-3", v, e) for v, e in [
        ({SBP: 129, DBP: 70}, OK), ({SBP: 130, DBP: 70}, WATCH), ({SBP: 110, DBP: 79}, OK),
        ({SBP: 110, DBP: 80}, WATCH), ({SBP: 130}, WATCH), ({SBP: 129}, UNKNOWN),
    ]],
    *[case("CV-4", v, e) for v, e in [
        ({SBP: 89, DBP: 70}, WATCH), ({SBP: 90, DBP: 70}, OK), ({SBP: 110, DBP: 59}, WATCH),
        ({SBP: 110, DBP: 60}, OK), ({SBP: 89}, WATCH), ({SBP: 90}, UNKNOWN),
    ]],
    *[case("CV-5", {HR: v}, e) for v, e in [(59, WATCH), (60, OK), (100, OK), (101, WATCH)]],
    case("CV-5", {}, UNKNOWN),
    # CV-6 (supine 120 mmHg / 70 bpm)
    *[case("CV-6", {OS: s, E.SYSTOLIC_SUPINE: 120, E.SYSTOLIC_STANDING: st,
                    E.HEART_RATE_SUPINE: 70, E.HEART_RATE_STANDING: hr}, e)
      for s, st, hr, e in [
          (True, 101, 99, OK), (True, 100, 99, ACTION), (True, 101, 100, ACTION),
          (False, 80, 120, OK), (True, 130, 70, OK),
      ]],
    case("CV-6", {}, UNKNOWN),
    case("CV-6", {OS: True, E.SYSTOLIC_SUPINE: 120, E.SYSTOLIC_STANDING: 101}, UNKNOWN),
    case("CV-6", {OS: True, E.SYSTOLIC_SUPINE: 120, E.SYSTOLIC_STANDING: 100}, ACTION),
    # CV-7 / CV-8 (preflight 100)
    *[case(r, {E.VO2_MAX: now, E.VO2_MAX_PREFLIGHT: 100}, exp[i])
      for now, exp in VO2_TABLE for i, r in enumerate(("CV-7", "CV-8"))],
    case("CV-7", {E.VO2_MAX: 40}, UNKNOWN), case("CV-8", {E.VO2_MAX: 40, E.VO2_MAX_PREFLIGHT: 0}, UNKNOWN),
    # BL-1
    case("BL-1", {E.HEMOGLOBIN_G_DL: 11.9, E.HEMOGLOBIN_LAB_LOWER_LIMIT_G_DL: 12}, WATCH),
    case("BL-1", {E.HEMOGLOBIN_G_DL: 12, E.HEMOGLOBIN_LAB_LOWER_LIMIT_G_DL: 12}, OK),
    case("BL-1", {E.HEMOGLOBIN_G_DL: 12}, UNKNOWN),
    # MT-1 .. MT-4
    *[case(r, {C.BLOOD_GLUCOSE: g}, exp[i])
      for g, exp in GLUCOSE_TABLE for i, r in enumerate(("MT-1", "MT-2", "MT-3", "MT-4"))],
    # MT-5, MT-6, MT-7
    *[case("MT-5", {E.HBA1C_PERCENT: v}, e) for v, e in [(5.6, OK), (5.7, WATCH), (6.4, WATCH), (6.5, ACTION)]],
    *[case("MT-6", {E.ENERGY_DEFICIT_DAYS: v}, e) for v, e in [(2, OK), (3, WATCH)]],
    *[case("MT-7", {C.BODY_MASS_INDEX: v}, e) for v, e in
      [(18.4, WATCH), (18.5, OK), (29.9, OK), (30, WATCH)]],
    # MT-8 by sex (Sex enum and strings), sex missing or unreadable
    *[case("MT-8", {C.BODY_FAT_PERCENTAGE: v, SEX: s} if s else {C.BODY_FAT_PERCENTAGE: v}, e)
      for v, s, e in [
          (4.9, M, ACTION), (5, M, OK), (12.9, F, ACTION), (13, F, OK), (12.9, "f", ACTION),
          (5, " F ", ACTION), (5, "m", OK), (4.9, None, ACTION), (5, None, UNKNOWN),
          (12.9, None, UNKNOWN), (13, None, OK), (5, "x", UNKNOWN), (5, 1, UNKNOWN),
      ]],
    # MT-9: body fat by sex, WHtR (height 200: waist 98 -> 0.49, 100 -> 0.5)
    *[case("MT-9", {C.BODY_FAT_PERCENTAGE: v, SEX: s, E.WAIST_CIRCUMFERENCE_CM: 80, C.HEIGHT: 200}, e)
      for v, s, e in [
          (24.9, M, OK), (25, M, WATCH), (31.9, F, OK), (32, F, WATCH),
          (25, F, OK), (31.9, "m", WATCH), (32, None, WATCH), (24.9, None, OK), (28, None, UNKNOWN),
      ]],
    *[case("MT-9", {E.WAIST_CIRCUMFERENCE_CM: w, C.HEIGHT: 200}, e)
      for w, e in [(98, UNKNOWN), (100, WATCH)]],
    case("MT-9", {C.BODY_FAT_PERCENTAGE: 10, SEX: M}, UNKNOWN),
    case("MT-9", {C.BODY_FAT_PERCENTAGE: 10, SEX: M, E.WAIST_CIRCUMFERENCE_CM: 100, C.HEIGHT: 200}, WATCH),
    case("MT-9", {E.WAIST_CIRCUMFERENCE_CM: 100, C.HEIGHT: 0}, UNKNOWN),
    # MS-1 (preflight 100 %)
    *[case("MS-1", {C.MUSCLE_MASS_PERCENTAGE: n, E.MUSCLE_MASS_PERCENTAGE_PREFLIGHT: 100}, e)
      for n, e in [(90, OK), (89.9, WATCH), (95, OK)]],
    case("MS-1", {C.MUSCLE_MASS_PERCENTAGE: 40}, UNKNOWN),
    case("MS-1", {C.MUSCLE_MASS_PERCENTAGE: 40, E.MUSCLE_MASS_PERCENTAGE_PREFLIGHT: 0}, UNKNOWN),
    # MS-2 grip by sex / no sex
    *[case("MS-2", {E.GRIP_STRENGTH_KG: v, SEX: s} if s else {E.GRIP_STRENGTH_KG: v}, e)
      for v, s, e in [
          (26.9, M, ACTION), (27, M, OK), (15.9, F, ACTION), (16, F, OK), (20, F, OK), (20, M, ACTION),
          (15.9, None, ACTION), (16, None, UNKNOWN), (26.9, None, UNKNOWN), (27, None, OK),
      ]],
    # BN-1 (preflight 100, 10 months): 15 % -> 1.5 %/month
    case("BN-1", {E.BONE_DENSITY_PREFLIGHT: 100, C.BONE_DENSITY_CALCIUM: 85, E.MONTHS_IN_FLIGHT: 10}, OK),
    case("BN-1", {E.BONE_DENSITY_PREFLIGHT: 100, C.BONE_DENSITY_CALCIUM: 84, E.MONTHS_IN_FLIGHT: 10}, WATCH),
    case("BN-1", {E.BONE_DENSITY_PREFLIGHT: 100, C.BONE_DENSITY_CALCIUM: 84, E.MONTHS_IN_FLIGHT: 0}, UNKNOWN),
    case("BN-1", {E.BONE_DENSITY_PREFLIGHT: 100, C.BONE_DENSITY_CALCIUM: 84}, UNKNOWN),
    # BN-2 / BN-3 T-score
    *[case(r, {E.T_SCORE: t}, exp[i])
      for t, exp in [(-0.9, (OK, OK)), (-1.0, (OK, OK)), (-1.01, (WATCH, OK)), (-2.49, (WATCH, OK)),
                     (-2.5, (OK, ACTION)), (-3, (OK, ACTION))]
      for i, r in enumerate(("BN-2", "BN-3"))],
    case("BN-2", {}, UNKNOWN),
    *[case("BN-4", {E.VITAMIN_D_NG_ML: v}, e) for v, e in [(19.9, WATCH), (20, OK)]],
    # KD-1 per phase
    case("KD-1", {}, WATCH, PHASES.RETURN), case("KD-1", {}, OK, PHASES.ADAPTATION),
    case("KD-1", {}, OK, PHASES.LONG_DURATION), case("KD-1", {}, UNKNOWN, PHASES.UNKNOWN),
    # SL-1 (age present / absent / under 18 falls back to the 7 h constant)
    *[case("SL-1", {C.SLEEP_HOURS: h, **a}, e)
      for h, a, e in [(6.99, {C.AGE: 30}, WATCH), (7, {C.AGE: 30}, OK), (6.99, {}, WATCH), (7, {}, OK),
                      (6.99, {C.AGE: 17}, WATCH), (7, {C.AGE: 17}, OK)]],
    case("SL-1", {C.AGE: 30}, UNKNOWN),
    # SL-2: hours and debt (4 days of 4.5 h = exactly 10 h of debt)
    *[case("SL-2", {C.SLEEP_HOURS: h, **x}, e) for h, x, e in [
        (6, {}, ACTION), (6.01, {}, OK), (7, {E.SLEEP_HOURS_HISTORY: (4.5,) * 4}, OK),
        (7, {E.SLEEP_HOURS_HISTORY: (4.4,) * 4}, ACTION), (8, {E.SLEEP_HOURS_HISTORY: (4.4,) * 4, C.AGE: 30}, ACTION),
        (7, {E.SLEEP_HOURS_HISTORY: (4.5,) * 4, C.AGE: 30}, OK), (7, {E.SLEEP_HOURS_HISTORY: (4.4,) * 4, C.AGE: 17}, ACTION),
        (7, {E.SLEEP_HOURS_HISTORY: ()}, OK),
    ]],
    case("SL-2", {E.SLEEP_HOURS_HISTORY: (4.4,) * 4}, ACTION), case("SL-2", {}, UNKNOWN),
    # SL-3 (time in bed 10 h: 8.5 h = 85 %)
    *[case("SL-3", {C.SLEEP_HOURS: h, E.TIME_IN_BED_HOURS: 10, E.SLEEP_LATENCY_MIN: lat}, e)
      for h, lat, e in [(8.5, 30, OK), (8.49, 30, WATCH), (8.5, 31, WATCH), (8.49, 31, WATCH)]],
    case("SL-3", {E.SLEEP_LATENCY_MIN: 31}, WATCH), case("SL-3", {E.SLEEP_LATENCY_MIN: 30}, UNKNOWN),
    case("SL-3", {C.SLEEP_HOURS: 9, E.TIME_IN_BED_HOURS: 8, E.SLEEP_LATENCY_MIN: 10}, UNKNOWN),
    # CG-1
    *[case("CG-1", {E.PVT_LAPSES: 5 + inc, E.PVT_LAPSES_BASELINE: 5}, e)
      for inc, e in [(0, OK), (1, OK), (2, WATCH), (4, WATCH), (5, ACTION), (9, ACTION)]],
    case("CG-1", {E.PVT_LAPSES: 5}, UNKNOWN),
    # PS-1 / PS-2 / PS-3
    *[case("PS-1", {C.STRESS_LEVEL: s}, e) for s, e in [(3.9, OK), (4, WATCH), (6.9, WATCH), (7, OK)]],
    *[case("PS-2", {C.STRESS_LEVEL: s}, e) for s, e in [(3.9, OK), (6.9, OK), (7, ACTION)]],
    case("PS-2", {C.STRESS_LEVEL: 5, E.PSS10_ANSWERS: (4, 4, 2, 0, 0, 0, 0, 0, 0, 0)}, OK),
    case("PS-2", {C.STRESS_LEVEL: 5, E.PSS10_ANSWERS: (4, 4, 3, 0, 0, 0, 0, 0, 0, 0)}, ACTION),
    case("PS-2", {E.PSS10_ANSWERS: (4, 4, 3, 0, 0, 0, 0, 0, 0, 0)}, ACTION),
    case("PS-2", {E.PSS10_ANSWERS: (4, 4, 2, 0, 0, 0, 0, 0, 0, 0)}, UNKNOWN),
    case("PS-2", {C.STRESS_LEVEL: 5, E.PSS10_ANSWERS: (4, 4, 3)}, OK),
    case("PS-2", {E.PSS10_ANSWERS: (4,) * 9}, UNKNOWN),
    case("PS-2", {E.PSS10_ANSWERS: (5,) + (4,) * 9}, UNKNOWN),
    case("PS-2", {E.PSS10_ANSWERS: (0.5,) * 10}, UNKNOWN),
    *[case("PS-3", {E.HRV_RMSSD_MS: n, E.HRV_RMSSD_BASELINE_MS: 100}, e)
      for n, e in [(80, WATCH), (80.1, OK), (50, WATCH), (120, OK)]],
    case("PS-3", {E.HRV_RMSSD_MS: 80, E.HRV_RMSSD_BASELINE_MS: 0}, UNKNOWN),
    # RD-1 .. RD-3 with the prior dose present
    *[case(r, {C.MISSION_RADIATION_LEVEL: 100, E.PRIOR_CAREER_DOSE_MSV: dose - 100}, exp[i])
      for dose, exp in RADIATION_TABLE for i, r in enumerate(("RD-1", "RD-2", "RD-3"))],
    # RD lower bound (prior dose missing): fire if already reached, never OK
    *[case(r, {C.MISSION_RADIATION_LEVEL: 100}, UNKNOWN) for r in ("RD-1", "RD-2", "RD-3")],
    case("RD-1", {C.MISSION_RADIATION_LEVEL: 350}, WATCH), case("RD-2", {C.MISSION_RADIATION_LEVEL: 350}, UNKNOWN),
    case("RD-2", {C.MISSION_RADIATION_LEVEL: 490}, ACTION), case("RD-3", {C.MISSION_RADIATION_LEVEL: 610}, URGENT),
    case("RD-3", {E.PRIOR_CAREER_DOSE_MSV: 100}, UNKNOWN),
    # EY-1 / EY-2
    *[case(r, v, e) for r, k, in [("EY-1", E.SANS_NEW_FINDINGS), ("EY-2", E.SANS_GRADE_WORSENED)]
      for v, e in [({k: True}, ACTION if r == "EY-1" else URGENT), ({k: False}, OK), ({}, UNKNOWN),
                   ({k: "yes"}, UNKNOWN), ({k: 1}, UNKNOWN)]],
]


@pytest.mark.parametrize(("rule_id", "values", "expected", "phase"), THRESHOLD_CASES)
def test_rule_status_at_threshold_boundaries(rule_id, values, expected, phase):
    assert run(rule_id, values, phase) is expected


# ---------------------------------------------------------------- rules table integrity
def test_there_are_37_rules_with_unique_ids_in_spec_order():
    ids = [r.id for r in RULES]
    assert len(ids) == 37 and len(set(ids)) == 37
    assert ids[:9] == ["CV-1", "CV-2", "CV-3", "CV-4", "CV-5", "CV-6", "CV-7", "CV-8", "BL-1"]
    assert ids[-3:] == ["RD-3", "EY-1", "EY-2"]


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_every_rule_has_complete_metadata(rule):
    assert rule.source and rule.actions and rule.protects and rule.inputs and rule.phases
    assert all(isinstance(a, str) and a for a in rule.actions)
    assert rule.condition and rule.variable and callable(rule.assess)
    assert rule.status >= WATCH


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_every_rule_returns_unknown_on_an_empty_context(rule):
    ctx = make_context({}, PHASES.UNKNOWN)
    assert rec.evaluate_rule(rule, ctx).status is UNKNOWN


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
@pytest.mark.parametrize("junk", ["abc", float("nan"), (), [], object()], ids=["str", "nan", "tuple", "list", "obj"])
def test_every_rule_treats_unusable_values_as_unknown_without_raising(rule, junk):
    ctx = make_context({key: junk for key in rule.inputs})
    assert rec.evaluate_rule(rule, ctx).status is UNKNOWN


def test_rule_by_id_returns_rule_and_unknown_id_raises_key_error():
    assert rule_by_id("MT-1") is RULES[[r.id for r in RULES].index("MT-1")]
    with pytest.raises(KeyError):
        rule_by_id("XX-9")


CONDITION_NUMBERS = {
    "CV-1": (rr.BP_CRISIS_SYSTOLIC, rr.BP_CRISIS_DIASTOLIC), "CV-3": (rr.BP_HIGH_SYSTOLIC, rr.BP_HIGH_DIASTOLIC),
    "CV-4": (rr.BP_LOW_SYSTOLIC, rr.BP_LOW_DIASTOLIC), "CV-5": (rr.RESTING_HR_LOW, rr.RESTING_HR_HIGH),
    "CV-6": (rr.ORTHOSTATIC_SBP_DROP_MMHG, rr.ORTHOSTATIC_HR_RISE_BPM), "CV-7": (80,),
    "CV-8": (rr.VO2_WATCH_PERCENT,), "MT-1": (rr.GLUCOSE_LEVEL2_HYPO,), "MT-2": (rr.GLUCOSE_LEVEL1_HYPO,),
    "MT-3": (rr.GLUCOSE_PREDIABETES,), "MT-4": (rr.GLUCOSE_DIABETES,),
    "MT-5": (rr.HBA1C_PREDIABETES, rr.HBA1C_DIABETES), "MT-6": (rr.ENERGY_DEFICIT_MIN_DAYS,),
    "MT-7": (rr.BMI_UNDERWEIGHT, rr.BMI_OBESE), "MT-9": (25, 32, rr.WHTR_HIGH),
    "MS-1": (rr.MUSCLE_DROP_PERCENT,), "MS-2": (27, 16), "BN-1": (rr.BONE_LOSS_RATE_MAX,),
    "BN-2": (rr.T_SCORE_NORMAL_MIN, rr.T_SCORE_OSTEOPOROSIS), "BN-3": (rr.T_SCORE_OSTEOPOROSIS,),
    "BN-4": (rr.VITAMIN_D_LOW_NG_ML,), "SL-2": (rr.SLEEP_SHORT_HOURS, rr.SLEEP_DEBT_MAX_HOURS),
    "SL-3": (rr.SLEEP_EFFICIENCY_MIN, rr.SLEEP_LATENCY_MAX_MIN),
    "CG-1": (rr.PVT_LAPSE_INCREASE_WATCH, rr.PVT_LAPSE_INCREASE_ACTION),
    "PS-1": (rr.STRESS_MODERATE_MIN,), "PS-2": (rr.STRESS_HIGH_MIN, rr.PSS10_HIGH_MIN),
    "PS-3": (rr.HRV_DROP_PERCENT,), "RD-1": (rr.RADIATION_WATCH_PERCENT,),
    "RD-2": (rr.RADIATION_ACTION_PERCENT,), "RD-3": (rr.RADIATION_URGENT_PERCENT,),
}


@pytest.mark.parametrize(("rule_id", "numbers"), CONDITION_NUMBERS.items())
def test_rule_condition_text_contains_its_threshold_numbers(rule_id, numbers):
    condition = rule_by_id(rule_id).condition
    assert all(f"{n:g}" in condition or str(n) in condition for n in numbers)


# ---------------------------------------------------------------- validate_inputs
def test_validate_inputs_drops_none_and_rejects_bad_core_values():
    values = {SBP: 300, DBP: math.nan, HR: True, C.AGE: "35", C.BLOOD_GLUCOSE: None,
              C.HEIGHT: 180, SEX: "M", E.T_SCORE: -3, C.STRESS_LEVEL: None}
    clean, invalid = rec.validate_inputs(values)
    assert clean == {C.HEIGHT: 180, SEX: "M", E.T_SCORE: -3}
    assert invalid == (SBP, DBP, HR, C.AGE)


@pytest.mark.parametrize(("value", "valid"), [(69.9, False), (70, True), (250, True), (250.1, False)])
def test_validate_inputs_applies_definition_limits_inclusively(value, valid):
    clean, invalid = rec.validate_inputs({SBP: value})
    assert (SBP in clean) is valid and (SBP in invalid) is (not valid)


def test_validate_inputs_does_not_validate_extras_and_returns_new_dict():
    source = {E.GRIP_STRENGTH_KG: "heavy"}
    clean, invalid = rec.validate_inputs(source)
    assert clean == source and clean is not source and invalid == ()


# ---------------------------------------------------------------- evaluate_rule
@pytest.mark.parametrize("error", [ValueError("v"), TypeError("t"), ZeroDivisionError("z")])
def test_evaluate_rule_turns_data_errors_into_unknown_with_note(error):
    def boom(ctx):
        raise error
    result_ = rec.evaluate_rule(fake_rule("T-1", inputs=(E.SEX,), assess=boom), make_context({}))
    assert result_.status is UNKNOWN and result_.note.startswith("data error:") and result_.missing == (E.SEX,)


def test_evaluate_rule_lists_missing_inputs_only_when_unknown():
    rule = fake_rule("T-1", inputs=(E.SEX, E.T_SCORE), assess=lambda ctx: UNKNOWN)
    ctx = make_context({E.T_SCORE: -1})
    assert rec.evaluate_rule(rule, ctx).missing == (E.SEX,)
    ok_rule = fake_rule("T-2", inputs=(E.SEX,), assess=lambda ctx: OK)
    assert rec.evaluate_rule(ok_rule, ctx).missing == ()


def test_negative_prior_dose_is_data_error_and_unknown():
    ctx = make_context({C.MISSION_RADIATION_LEVEL: 100, E.PRIOR_CAREER_DOSE_MSV: -50})
    outcome = rec.evaluate_rule(rule_by_id("RD-1"), ctx)
    assert outcome.status is UNKNOWN and "data error" in outcome.note


def test_assess_survives_bad_data_in_every_input():
    values = {k: "bad" for k in E} | {C.MISSION_RADIATION_LEVEL: 10}
    values[E.PRIOR_CAREER_DOSE_MSV] = -5
    values[E.PSS10_ANSWERS] = (1, 2)
    assessment = rec.assess(values)
    assert assessment.overall is not OK and len(assessment.results) == 37


# ---------------------------------------------------------------- assess: UNKNOWN handling
def test_assess_empty_gives_overall_unknown_and_all_systems_unknown():
    assessment = rec.assess({})
    assert assessment.overall is UNKNOWN and not assessment.multi_system_review
    assert [s.system for s in assessment.systems] == list(SYSTEM_ORDER)
    assert all(s.status is UNKNOWN for s in assessment.systems)
    assert assessment.recommendations == () and assessment.provided == frozenset()
    assert not assessment.is_complete


def test_measure_this_on_empty_input_lists_inputs_with_their_rule_ids():
    items = {m.key: m for m in rec.assess({}).measure_this}
    assert items[SBP].rule_ids == ("CV-1", "CV-2", "CV-3", "CV-4")
    assert items[C.AGE].rule_ids == ("SL-1", "SL-2")
    assert items[C.BODY_WEIGHT].rule_ids == () and items[C.BODY_WEIGHT].label == C.BODY_WEIGHT.value
    assert items[E.SEX].label == E.SEX.value and items[E.SEX].rule_ids == ("MT-8", "MT-9", "MS-2")
    keys = [m.key for m in rec.assess({}).measure_this]
    assert all(isinstance(k, C) for k in keys[:14]) and all(isinstance(k, E) for k in keys[14:])


def test_collect_missing_alone_skips_core_characteristics_no_rule_reads():
    results = rec.evaluate_rules(make_context({}))
    keys = {m.key for m in rec.collect_missing(results)}
    assert C.BODY_WEIGHT not in keys and SBP in keys and E.MISSION_PHASE in keys


def test_invalid_core_value_is_reported_as_out_of_range_in_measure_this():
    assessment = rec.assess({SBP: 300})
    item = next(m for m in assessment.measure_this if m.key is SBP)
    assert assessment.invalid_inputs == (SBP,) and SBP not in assessment.provided
    assert item.label == SBP.value + rec.OUT_OF_RANGE_SUFFIX and "CV-1" in item.rule_ids


def test_healthy_full_core_data_is_overall_ok_but_not_complete():
    assessment = rec.assess(HEALTHY)
    assert assessment.overall is OK and not assessment.is_complete
    assert assessment.recommendations == () and not assessment.multi_system_review
    assert system_map(assessment)[BodySystem.HEART_VESSELS].status is OK


def test_missing_core_data_prevents_overall_ok():
    partial = {k: v for k, v in HEALTHY.items() if k is not C.BLOOD_GLUCOSE}
    assert rec.assess(partial).overall is UNKNOWN
    assert system_map(rec.assess(partial))[BodySystem.METABOLISM].status is UNKNOWN


def test_assess_is_complete_when_nothing_left_to_measure():
    only_core = rec.assess({}, rules=())
    assert only_core.measure_this and not only_core.is_complete
    full = {**HEALTHY, **{k: 1 for k in E}}
    assert rec.assess(full, rules=()).is_complete


# ---------------------------------------------------------------- escalation, multi-system, overall
def _brain_rules(count: int, status: Status = WATCH):
    return tuple(fake_rule(f"W-{i}", status) for i in range(count))


def test_three_watch_on_one_system_escalates_to_action():
    brain = system_map(rec.assess({}, rules=_brain_rules(3)))[BodySystem.BRAIN]
    assert brain.status is ACTION and brain.escalated and brain.rule_ids == ("W-0", "W-1", "W-2")


def test_two_watch_on_one_system_stays_watch():
    brain = system_map(rec.assess({}, rules=_brain_rules(2)))[BodySystem.BRAIN]
    assert brain.status is WATCH and not brain.escalated


def test_watch_does_not_escalate_when_higher_status_present():
    rules = (*_brain_rules(3), fake_rule("A-1", ACTION))
    brain = system_map(rec.assess({}, rules=rules))[BodySystem.BRAIN]
    assert brain.status is ACTION and not brain.escalated


def test_ok_system_with_unknown_core_rule_is_unknown():
    needs_core = fake_rule("U-1", inputs=(C.AGE,), assess=lambda c: UNKNOWN)
    fine = fake_rule("O-1", assess=lambda c: OK)
    assert system_map(rec.assess({}, rules=(needs_core, fine)))[BodySystem.BRAIN].status is UNKNOWN
    needs_extra = fake_rule("U-2", inputs=(E.SEX,), assess=lambda c: UNKNOWN)
    assert system_map(rec.assess({}, rules=(needs_extra, fine)))[BodySystem.BRAIN].status is OK


def _systems(*statuses: Status) -> tuple[rec.SystemStatus, ...]:
    return tuple(rec.SystemStatus(s, st, ()) for s, st in zip(SYSTEM_ORDER, statuses))


@pytest.mark.parametrize(("statuses", "expected"), [
    ((ACTION, ACTION), True), ((ACTION,), False), ((URGENT, ACTION), True), ((URGENT,), False),
    ((URGENT, URGENT), True), ((WATCH, WATCH, WATCH), False), ((ACTION, WATCH, UNKNOWN), False),
])
def test_multi_system_review_needs_action_or_worse_on_two_systems(statuses, expected):
    assert rec.needs_multi_system_review(_systems(*statuses)) is expected


def test_assess_sets_multi_system_flag_from_systems():
    rules = (fake_rule("A-1", ACTION, (BodySystem.BRAIN,)), fake_rule("A-2", ACTION, (BodySystem.EYES,)))
    assert rec.assess({}, rules=rules).multi_system_review is True
    assert rec.assess({}, rules=rules[:1]).multi_system_review is False


@pytest.mark.parametrize(("statuses", "core_missing", "expected"), [
    ((OK, WATCH), False, WATCH), ((OK, OK), False, OK), ((OK, OK), True, UNKNOWN),
    ((WATCH, UNKNOWN), True, WATCH), ((UNKNOWN, UNKNOWN), False, UNKNOWN), ((URGENT, OK), True, URGENT),
])
def test_overall_status_is_highest_known_and_never_ok_with_missing_core(statuses, core_missing, expected):
    assert rec.overall_status(_systems(*statuses), core_missing) is expected


# ---------------------------------------------------------------- combinations
def test_sleep_deficit_and_high_stress_raise_each_rule_one_level():
    values = {C.SLEEP_HOURS: 6, C.STRESS_LEVEL: 8}
    plain = rec.evaluate_rules(make_context(values))
    combined = by_id(rec.assess(values))
    assert {r.rule.id: r.status for r in plain}["SL-1"] is WATCH
    assert (combined["SL-1"], combined["SL-2"], combined["PS-2"]) == (ACTION, URGENT, URGENT)
    notes = {r.rule.id: r.note for r in rec.assess(values).results}
    assert notes["SL-1"] == notes["SL-2"] == notes["PS-2"] == rec.SLEEP_STRESS_NOTE


def test_sleep_stress_combination_only_raises_firing_sleep_rules():
    combined = by_id(rec.assess({C.SLEEP_HOURS: 6.5, C.STRESS_LEVEL: 8}))
    assert (combined["SL-1"], combined["SL-2"], combined["PS-2"]) == (ACTION, OK, URGENT)


@pytest.mark.parametrize("values", [
    {C.SLEEP_HOURS: 5, C.STRESS_LEVEL: 5}, {C.SLEEP_HOURS: 8, C.STRESS_LEVEL: 9}, {C.SLEEP_HOURS: 5},
])
def test_sleep_stress_combination_not_applied_without_both_parts(values):
    combined = by_id(rec.assess(values))
    assert combined["SL-1"] in (WATCH, OK, UNKNOWN) and combined["SL-2"] in (ACTION, OK, UNKNOWN)
    assert combined["PS-2"] in (ACTION, OK, UNKNOWN)
    assert all(r.note == "" for r in rec.assess(values).results)


def test_combination_is_capped_at_urgent_and_never_lowers():
    sl1, ps2 = fake_rule("SL-1"), fake_rule("PS-2")
    out = rec.apply_combinations((result(sl1, URGENT), result(ps2, URGENT)), make_context({}))
    assert [r.status for r in out] == [URGENT, URGENT]
    out = rec.apply_combinations((result(sl1, URGENT), result(ps2, ACTION)), make_context({}))
    assert [r.status for r in out] == [URGENT, URGENT]


RETURN_VALUES = {SBP: 85, DBP: 70, HR: 105}


def test_return_phase_low_bp_and_high_hr_makes_cv6_action():
    assessment = rec.assess(RETURN_VALUES, PHASES.RETURN)
    cv6 = next(r for r in assessment.results if r.rule.id == "CV-6")
    assert cv6.status is ACTION and cv6.note == rec.RETURN_ORTHOSTATIC_NOTE and cv6.missing == ()


@pytest.mark.parametrize("phase", [PHASES.LONG_DURATION, PHASES.ADAPTATION, PHASES.UNKNOWN])
def test_return_orthostatic_combination_not_applied_in_other_phases(phase):
    assert by_id(rec.assess(RETURN_VALUES, phase))["CV-6"] is UNKNOWN


@pytest.mark.parametrize("values", [
    {SBP: 85, DBP: 70, HR: 100}, {SBP: 110, DBP: 70, HR: 105}, {SBP: 85, DBP: 70},
])
def test_return_orthostatic_combination_needs_low_bp_and_hr_above_100(values):
    assert by_id(rec.assess(values, PHASES.RETURN))["CV-6"] is UNKNOWN


def test_return_combination_keeps_higher_status_of_cv6():
    cv4, cv6 = rule_by_id("CV-4"), fake_rule("CV-6", URGENT)
    ctx = make_context({HR: 120}, PHASES.RETURN)
    out = rec.apply_combinations((result(cv4, WATCH), result(cv6, URGENT)), ctx)
    assert out[1].status is URGENT and out[1].note == ""


# ---------------------------------------------------------------- recommendations ordering
def test_recommendations_sorted_by_status_descending_first():
    rules = (fake_rule("A-1", WATCH), fake_rule("B-1", URGENT), fake_rule("C-1", ACTION))
    recs = rec.build_recommendations(tuple(result(r, r.status) for r in rules), PHASES.UNKNOWN)
    assert [r.rule_ids[0] for r in recs] == ["B-1", "C-1", "A-1"]


def test_phase_relevant_recommendations_come_first_within_same_status():
    first = fake_rule("A-1", ACTION, (BodySystem.HEART_VESSELS,), phases=(PHASES.RETURN,))
    second = fake_rule("B-1", ACTION, (BodySystem.IMMUNE,), phases=(PHASES.LONG_DURATION,))
    recs = rec.build_recommendations((result(first, ACTION), result(second, ACTION)), PHASES.LONG_DURATION)
    assert [r.rule_ids[0] for r in recs] == ["B-1", "A-1"]
    assert [r.phase_relevant for r in recs] == [True, False]


def test_unknown_phase_makes_nothing_phase_relevant():
    rule = fake_rule("A-1", ACTION, phases=(PHASES.RETURN,))
    recs = rec.build_recommendations((result(rule, ACTION),), PHASES.UNKNOWN)
    assert recs[0].phase_relevant is False


def test_system_order_then_rule_order_break_ties():
    bones = fake_rule("A-1", ACTION, (BodySystem.BONES,))
    heart = fake_rule("B-1", ACTION, (BodySystem.HEART_VESSELS,))
    twin1, twin2 = fake_rule("C-1", ACTION, (BodySystem.EYES,)), fake_rule("D-1", ACTION, (BodySystem.EYES,))
    results = tuple(result(r, ACTION) for r in (bones, heart, twin1, twin2))
    recs = rec.build_recommendations(results, PHASES.UNKNOWN)
    assert [r.rule_ids[0] for r in recs] == ["B-1", "C-1", "D-1", "A-1"]


def test_only_watch_or_worse_results_produce_recommendations():
    rules = [fake_rule("A-1", OK), fake_rule("B-1", UNKNOWN), fake_rule("C-1", WATCH)]
    recs = rec.build_recommendations(tuple(result(r, r.status) for r in rules), PHASES.UNKNOWN)
    assert [r.rule_ids for r in recs] == [("C-1",)]


def test_identical_actions_merge_into_one_recommendation_listing_both_rules_and_systems():
    values = {C.MUSCLE_MASS_PERCENTAGE: 40, E.MUSCLE_MASS_PERCENTAGE_PREFLIGHT: 50,
              C.BONE_DENSITY_CALCIUM: 0.8, E.BONE_DENSITY_PREFLIGHT: 1.0, E.MONTHS_IN_FLIGHT: 5}
    rules = (rule_by_id("MS-1"), rule_by_id("BN-1"))
    assessment = rec.assess(values, PHASES.LONG_DURATION, rules=rules)
    merged = [r for r in assessment.recommendations if r.action == rr.ACTION_RESISTANCE_EXERCISE]
    assert len(merged) == 1 and merged[0].rule_ids == ("MS-1", "BN-1")
    assert merged[0].systems == (BodySystem.BONES, BodySystem.MUSCLES) and len(merged[0].sources) == 2
    assert merged[0].phase_relevant and merged[0].status is WATCH
    assert len(assessment.recommendations) == 2


def test_merged_recommendation_takes_highest_status_and_unique_sources():
    one = fake_rule("A-1", WATCH, (BodySystem.BRAIN,), actions=("shared",))
    two = fake_rule("B-1", ACTION, (BodySystem.BRAIN,), actions=("shared", "own"))
    recs = rec.build_recommendations((result(one, WATCH), result(two, ACTION)), PHASES.UNKNOWN)
    shared = next(r for r in recs if r.action == "shared")
    assert shared.status is ACTION and shared.systems == (BodySystem.BRAIN,)
    assert recs[0].action == "shared"


# ---------------------------------------------------------------- characteristic_status
def test_characteristic_status_missing_ok_and_firing():
    glucose_low = rec.assess({C.BLOOD_GLUCOSE: 50, SBP: 115, DBP: 75, C.SLEEP_HOURS: 8})
    assert rec.characteristic_status(glucose_low, C.BLOOD_GLUCOSE) is URGENT
    assert rec.characteristic_status(glucose_low, C.SLEEP_HOURS) is OK
    assert rec.characteristic_status(glucose_low, C.STRESS_LEVEL) is UNKNOWN
    assert rec.characteristic_status(glucose_low, C.BODY_WEIGHT) is UNKNOWN


def test_characteristic_status_ignores_unknown_rule_results_and_invalid_values():
    assessment = rec.assess({SBP: 85, DBP: 70})
    assert rec.characteristic_status(assessment, SBP) is WATCH
    assert rec.characteristic_status(rec.assess({SBP: 300}), SBP) is UNKNOWN


def test_characteristic_status_provided_but_read_by_no_rule_is_ok():
    assert rec.characteristic_status(rec.assess({C.BODY_WEIGHT: 75}), C.BODY_WEIGHT) is OK


# ---------------------------------------------------------------- immutability
def test_assess_does_not_mutate_input_mapping():
    values = {**HEALTHY, SBP: 190, HS: False}
    values[E.PSS10_ANSWERS] = (1, 2, 3)
    values[C.BLOOD_GLUCOSE] = None
    snapshot = copy.deepcopy(values)
    rec.assess(values, PHASES.RETURN)
    assert values == snapshot and list(values) == list(snapshot)


@pytest.mark.parametrize("obj", [
    rec.RuleResult(RULES[0], OK), rec.SystemStatus(BodySystem.BRAIN, OK, ()),
    rec.Recommendation("a", WATCH, (), (), (), False), rec.MissingInput(SBP, "x", ()),
    rec.assess({}), RULES[0], make_context({}),
], ids=lambda o: type(o).__name__)
def test_result_dataclasses_are_frozen(obj):
    field = dataclasses.fields(obj)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, field, None)


def test_rule_context_values_are_read_only_and_detached_from_source():
    source = {SBP: 120}
    ctx = make_context(source, PHASES.RETURN)
    with pytest.raises(TypeError):
        ctx.values[SBP] = 1  # type: ignore[index]
    source[SBP] = 999
    assert ctx.get(SBP) == 120 and ctx.get(DBP) is None
    assert ctx.values[E.MISSION_PHASE] == "return"


def test_make_context_drops_none_and_skips_phase_entry_when_unknown():
    ctx = make_context({SBP: None, DBP: 80})
    assert SBP not in ctx.values and E.MISSION_PHASE not in ctx.values and ctx.phase is PHASES.UNKNOWN


def test_core_definitions_cover_the_14_characteristics_used_by_the_engine():
    assert len(CHARACTERISTIC_DEFINITIONS) == 14
    assert all(d.characteristic in rec._CORE_CHARACTERISTICS for d in CHARACTERISTIC_DEFINITIONS)


# --- Regression tests added during integration --------------------------------


def test_characteristic_status_is_unknown_when_every_rule_reading_it_is_unknown() -> None:
    # Arrange: mission dose alone (20 mSv) cannot decide RD-1..RD-3 without the prior career dose
    values = {C.MISSION_RADIATION_LEVEL: 20.0}

    # Act
    assessment = rec.assess(values)

    # Assert
    assert rec.characteristic_status(assessment, C.MISSION_RADIATION_LEVEL) is UNKNOWN


def test_characteristic_status_is_ok_when_no_rule_reads_a_valid_value() -> None:
    # Arrange
    values = {C.BODY_WEIGHT: 75.0}

    # Act
    assessment = rec.assess(values)

    # Assert
    assert rec.characteristic_status(assessment, C.BODY_WEIGHT) is OK


def test_infinite_pss10_answer_gives_unknown_instead_of_crashing() -> None:
    # Arrange
    values = {C.STRESS_LEVEL: 3.0, E.PSS10_ANSWERS: (math.inf,) + (1,) * 9}

    # Act
    assessment = rec.assess(values)

    # Assert
    ps2 = next(r for r in assessment.results if r.rule.id == "PS-2")
    assert ps2.status in (UNKNOWN, OK)


@pytest.mark.parametrize("characteristic", [C.AGE, C.HEIGHT])
def test_context_only_characteristic_is_ok_even_when_the_rule_it_modifies_fires(characteristic) -> None:
    # Arrange: SL-1 (reads AGE) and MT-9 (reads HEIGHT via WHtR) both fire
    values = {C.AGE: 40.0, C.SLEEP_HOURS: 5.0, C.HEIGHT: 170.0, E.WAIST_CIRCUMFERENCE_CM: 100.0}

    # Act
    assessment = rec.assess(values)

    # Assert
    assert rec.characteristic_status(assessment, characteristic) is OK
