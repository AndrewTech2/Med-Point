import sqlite3

import analysis
from Caracteristici import create_table


def test_evaluate_pulse_thresholds():
    assert analysis.evaluate_pulse(49) == "Critical"
    assert analysis.evaluate_pulse(50) == "Warning"
    assert analysis.evaluate_pulse(60) == "Healthy"
    assert analysis.evaluate_pulse(100) == "Healthy"
    assert analysis.evaluate_pulse(101) == "Warning"
    assert analysis.evaluate_pulse(116) == "Critical"


def test_evaluate_systolic_thresholds():
    assert analysis.evaluate_systolic(89) == "Critical"
    assert analysis.evaluate_systolic(90) == "Healthy"
    assert analysis.evaluate_systolic(125) == "Warning"
    assert analysis.evaluate_systolic(130) == "Warning"
    assert analysis.evaluate_systolic(140) == "Critical"


def test_overall_status_prefers_worst_status():
    assert analysis.overall_status(["Healthy", "Healthy"]) == "Healthy"
    assert analysis.overall_status(["Healthy", "Warning"]) == "Warning"
    assert analysis.overall_status(["Healthy", "Warning", "Critical"]) == "Critical"


def test_analyze_row_ignores_missing_optional_fields_and_sets_overall_status():
    row = {
        analysis.PULSE_COLUMN: 72,
        analysis.SYSTOLIC_COLUMN: 118,
        analysis.BMI_COLUMN: 22.5,
    }
    result = analysis.analyze_row(row)
    assert result["Pulse"] == "Healthy"
    assert result["Systolic Pressure"] == "Healthy"
    assert result["BMI"] == "Healthy"
    assert result["Overall Status"] == "Healthy"


def test_load_data_reads_latest_measurement_from_english_schema(tmp_path):
    db_path = tmp_path / "test.db"
    with sqlite3.connect(db_path) as conn:
        create_table(conn)
        conn.execute(
            """INSERT INTO astronauts (first_name, last_name, age, height, weight)
            VALUES ('Andrei', 'Marin', 34, 180, 78)"""
        )
        astronaut_id = conn.execute("SELECT id FROM astronauts").fetchone()[0]
        conn.execute(
            """INSERT INTO measurement_history (
                astronaut_id, average_pulse, systolic_pressure, bmi,
                radiation_levels, bone_density
            ) VALUES (?, 72, 118, 22.5, 40, 1.1)""",
            (astronaut_id,),
        )

    row = analysis.load_data(db_path).iloc[0]
    assert row[analysis.FIRST_NAME_COLUMN] == "Andrei"
    assert row[analysis.LAST_NAME_COLUMN] == "Marin"
    result = analysis.analyze_row(row)
    assert result["Pulse"] == "Healthy"
    assert result["Radiation"] == "Healthy"
    assert result["Bone Density"] == "Healthy"
