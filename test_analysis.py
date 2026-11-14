import sqlite3
import tempfile
from pathlib import Path

import analysis


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


def test_migrate_database_adds_missing_columns():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE astronauti (id INTEGER PRIMARY KEY AUTOINCREMENT, nume TEXT, prenume TEXT, puls_mediu REAL, presiune_sistolica REAL, indice_masa_corporala REAL)"
        )
        conn.commit()
        conn.close()

        analysis.migrate_database(db_path)

        with sqlite3.connect(db_path) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(astronauti)").fetchall()]
            assert analysis.RADIATION_COLUMN in columns
            assert analysis.BONE_DENSITY_COLUMN in columns
