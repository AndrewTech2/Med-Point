"""Tests for calculations.py."""

import sqlite3
from contextlib import closing

import pytest

import calculations as calc
from Caracteristici import CHARACTERISTIC_DEFINITIONS, Characteristic, create_table, save_astronaut


def test_bmi_is_calculated_correctly_and_zero_height_is_rejected():
    assert calc.calculate_bmi(78, 180) == 24.1
    with pytest.raises(ValueError):
        calc.calculate_bmi(78, 0)


@pytest.mark.parametrize(
    ("bmi", "category"),
    [(18.4, "underweight"), (18.5, "normal"), (25, "overweight"), (30, "obese")],
)
def test_bmi_category_follows_who_thresholds(bmi, category):
    assert calc.bmi_category(bmi) == category


def test_body_composition():
    assert calc.fat_mass_kg(80, 25) == 20
    assert calc.lean_mass_kg(80, 25) == 60
    assert calc.muscle_mass_kg(80, 40) == 32


@pytest.mark.parametrize(
    ("systolic", "diastolic", "category"),
    [
        (118, 76, "normal"),
        (125, 75, "elevated"),
        (122, 80, "high (hypertension)"),
        (135, 70, "high (hypertension)"),
        (85, 70, "low"),
        (110, 55, "low"),
        (185, 100, "hypertensive crisis"),
        (150, 125, "hypertensive crisis"),
    ],
)
def test_blood_pressure_category(systolic, diastolic, category):
    assert calc.blood_pressure_category(systolic, diastolic) == category


def test_blood_pressure_rejects_systolic_not_above_diastolic():
    with pytest.raises(ValueError):
        calc.blood_pressure_category(70, 80)


def test_hypertensive_crisis_depends_on_symptoms():
    assert calc.evaluate_hypertensive_crisis(120, 80, True) == "no crisis"
    assert "EMERGENCY" in calc.evaluate_hypertensive_crisis(190, 100, True)
    assert "without symptoms" in calc.evaluate_hypertensive_crisis(190, 100, False)


def test_map_and_pulse_pressure():
    assert calc.mean_arterial_pressure(120, 80) == 93.3
    assert calc.pulse_pressure(120, 80) == 40


@pytest.mark.parametrize(
    ("pulse", "category"),
    [(59, "bradycardia"), (60, "normal"), (100, "normal"), (101, "tachycardia")],
)
def test_pulse_category(pulse, category):
    assert calc.pulse_category(pulse) == category


@pytest.mark.parametrize(
    ("glucose", "category"),
    [
        (53, "level 2 hypoglycemia"),
        (60, "level 1 hypoglycemia"),
        (70, "normal"),
        (99, "normal"),
        (100, "prediabetes"),
        (126, "high"),
    ],
)
def test_glucose_category(glucose, category):
    assert calc.glucose_category(glucose) == category


def test_max_heart_rate():
    assert calc.max_heart_rate_220(40) == 180
    assert calc.max_heart_rate_tanaka(40) == 180.0
    assert calc.percent_max_heart_rate(90, 180) == 50.0


def test_heart_rate_recovery_and_vo2():
    assert calc.heart_rate_recovery(150, 140) == 10
    assert calc.heart_rate_recovery_abnormal(10)
    assert not calc.heart_rate_recovery_abnormal(20)
    assert calc.vo2_percent_of_preflight(40, 50) == 80.0
    assert not calc.vo2_below_threshold(80.0)
    assert calc.vo2_below_threshold(79.9)


def test_orthostatic_response_returns_the_differences():
    response = calc.orthostatic_response(120, 60, 100, 85)
    assert (response.delta_systolic, response.delta_heart_rate) == (-20, 25)


def test_ffmi_and_normalisation():
    assert calc.ffmi(60, 180) == 18.52
    assert calc.ffmi_normalized(60, 180) == 18.52  # no adjustment at 1.8 m


def test_basal_metabolic_rate_mifflin_st_jeor():
    assert calc.basal_metabolic_rate(80, 180, 30, calc.Sex.M) == 1780.0
    assert calc.basal_metabolic_rate(60, 164, 30, calc.Sex.F) == 1314.0


def test_total_energy_expenditure_and_balance():
    tdee = calc.total_energy_expenditure(1780, calc.ActivityLevel.MODERATELY_ACTIVE)
    assert tdee == 2759.0
    assert calc.energy_balance(2500, tdee) == -259.0


def test_waist_to_height_ratio():
    assert calc.waist_to_height_ratio(85, 180) == 0.47


@pytest.mark.parametrize(
    ("t_score", "category"),
    [(0, "normal"), (-1.0, "normal"), (-1.5, "osteopenia"), (-2.5, "osteoporosis")],
)
def test_t_score_category(t_score, category):
    assert calc.t_score_category(t_score) == category


def test_bone_loss_rate_per_month():
    assert calc.bone_loss_rate(1.0, 0.946, 6) == 0.9


def test_grip_strength_low_depends_on_sex():
    assert calc.grip_strength_low(26, calc.Sex.M)
    assert not calc.grip_strength_low(26, calc.Sex.F)


def test_sleep_deficit_debt_and_efficiency():
    assert calc.sleep_deficit(6, 35) == 1.0
    assert calc.sleep_deficit(8, 35) == -1.0
    assert calc.cumulative_sleep_debt([6, 7, 8, 5], 35) == 2.0
    assert calc.sleep_efficiency(6.5, 8.5) == 76.5
    with pytest.raises(ValueError):
        calc.recommended_sleep_minimum(15)
    with pytest.raises(ValueError):
        calc.cumulative_sleep_debt([], 35)
    with pytest.raises(ValueError):
        calc.sleep_efficiency(9, 8)


@pytest.mark.parametrize(
    ("level", "category"),
    [(1, "low"), (3.9, "low"), (4, "moderate"), (7, "high")],
)
def test_stress_category(level, category):
    assert calc.stress_category(level) == category


def test_stress_category_rejects_values_outside_the_scale():
    with pytest.raises(ValueError):
        calc.stress_category(0)


def test_pss10_reverses_items_4_5_7_8():
    assert calc.pss10_score([0] * 10) == 16  # 4 reversed items x 4
    assert calc.pss10_score([4] * 10) == 24  # 6 x 4 + 4 x 0
    with pytest.raises(ValueError):
        calc.pss10_score([1] * 9)
    with pytest.raises(ValueError):
        calc.pss10_score([5] + [0] * 9)
    assert calc.pss10_category(13) == "low"
    assert calc.pss10_category(26) == "moderate"
    assert calc.pss10_category(27) == "high"


def test_hrv_rmssd():
    assert calc.hrv_rmssd([800, 810, 790]) == 15.81
    with pytest.raises(ValueError):
        calc.hrv_rmssd([800])


def test_pvt_lapses_uses_the_chosen_threshold():
    reaction_times = [300, 360, 499, 500, 800]
    assert calc.pvt_lapses(reaction_times) == 2
    assert calc.pvt_lapses(reaction_times, calc.PVT_B_LAPSE_THRESHOLD_MS) == 4


def test_radiation():
    assert calc.career_radiation_dose([100, 50.5]) == 150.5
    assert calc.radiation_limit_percent(150) == 25.0
    with pytest.raises(ValueError):
        calc.career_radiation_dose([10, -1])


def _astronaut_values() -> dict[Characteristic, float]:
    c = Characteristic
    return {
        c.AGE: 34,
        c.BODY_WEIGHT: 78,
        c.HEIGHT: 180,
        c.BODY_MASS_INDEX: 24.1,
        c.AVERAGE_HEART_RATE: 58,
        c.SYSTOLIC_BLOOD_PRESSURE: 118,
        c.DIASTOLIC_BLOOD_PRESSURE: 76,
        c.MUSCLE_MASS_PERCENTAGE: 44,
        c.BODY_FAT_PERCENTAGE: 14,
        c.STRESS_LEVEL: 3,
        c.MISSION_RADIATION_LEVEL: 20,
        c.BONE_DENSITY_CALCIUM: 1.1,
        c.BLOOD_GLUCOSE: 88,
        c.SLEEP_HOURS: 7.5,
    }


def test_calculate_from_characteristics_does_not_modify_the_input():
    values = _astronaut_values()
    copy = dict(values)
    result = calc.calculate_from_characteristics(values)
    assert values == copy
    assert result["bmi_calculated"] == 24.1
    assert result["blood_pressure_category"] == "normal"
    assert result["sleep_deficit_hours"] == -0.5


def test_load_astronauts_reads_back_what_was_saved(tmp_path):
    values = _astronaut_values()
    with closing(sqlite3.connect(tmp_path / "test.db")) as conn:
        create_table(conn)
        save_astronaut(conn, "Marin", "Andrei", values)
        loaded = calc.load_astronauts(conn)
    assert set(loaded) == {("Marin", "Andrei")}
    assert loaded[("Marin", "Andrei")] == {k: float(v) for k, v in values.items()}
    assert len(loaded[("Marin", "Andrei")]) == len(CHARACTERISTIC_DEFINITIONS)


def test_load_astronauts_returns_none_when_no_measurement_exists(tmp_path):
    with closing(sqlite3.connect(tmp_path / "unmeasured.db")) as conn:
        create_table(conn)
        conn.execute(
            "INSERT INTO astronauts (first_name, last_name, age, height, weight) "
            "VALUES ('Cristian', 'Stan', 42, 178, 80)"
        )
        loaded = calc.load_astronauts(conn)
    values = loaded[("Stan", "Cristian")]
    assert values[Characteristic.AGE] == 42
    assert values[Characteristic.BODY_WEIGHT] == 80
    assert values[Characteristic.BODY_MASS_INDEX] is None
    assert len(values) == len(CHARACTERISTIC_DEFINITIONS)
