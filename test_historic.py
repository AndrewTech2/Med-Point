import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from Caracteristici import Characteristic, create_table, save_astronaut
from calculations import connect_read_only
from historic import (
    Summary,
    find_astronaut_id,
    list_history,
    main,
    parse_characteristic,
    summarise,
)

BASE_VALUES = {
    Characteristic.AGE: 40,
    Characteristic.BODY_WEIGHT: 75,
    Characteristic.HEIGHT: 180,
    Characteristic.BODY_MASS_INDEX: 23.1,
    Characteristic.AVERAGE_HEART_RATE: 60,
    Characteristic.SYSTOLIC_BLOOD_PRESSURE: 120,
    Characteristic.DIASTOLIC_BLOOD_PRESSURE: 80,
    Characteristic.MUSCLE_MASS_PERCENTAGE: 40,
    Characteristic.BODY_FAT_PERCENTAGE: 18,
    Characteristic.STRESS_LEVEL: 3,
    Characteristic.MISSION_RADIATION_LEVEL: 10,
    Characteristic.BONE_DENSITY_CALCIUM: 1.2,
    Characteristic.BLOOD_GLUCOSE: 90,
    Characteristic.SLEEP_HOURS: 7,
}


def make_db(path: Path, pulses: list[float] = ()) -> Path:
    with closing(sqlite3.connect(path)) as conn:
        create_table(conn)
        conn.execute("INSERT INTO astronauts (first_name, last_name) VALUES ('Empty', 'Nobody')")
        for pulse in pulses:
            save_astronaut(
                conn, "Doe", "Jane", {**BASE_VALUES, Characteristic.AVERAGE_HEART_RATE: pulse}
            )
        conn.commit()
    return path


def astronaut_id(db: Path, name: str) -> int | None:
    with closing(connect_read_only(db)) as conn:
        return find_astronaut_id(conn, name)


def history_of(db: Path, name: str) -> list:
    with closing(connect_read_only(db)) as conn:
        return list_history(conn, find_astronaut_id(conn, name))


def test_empty_history_summarises_to_zero_count(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db")
    # Act
    history = history_of(db, "Nobody Empty")
    summary = summarise(history, Characteristic.AVERAGE_HEART_RATE)
    # Assert
    assert history == []
    assert summary == Summary(0, None, None, None, None, None, None)


def test_one_row_has_zero_change(tmp_path):
    db = make_db(tmp_path / "h.db", [64])
    history = history_of(db, "Doe Jane")
    summary = summarise(history, Characteristic.AVERAGE_HEART_RATE)
    assert len(history) == 1
    assert summary == Summary(1, 64, 64, 64, 64, 64, 0)


def test_several_rows_oldest_first_and_none_ignored(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db", [70, 60, 80])
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE measurement_history SET average_pulse = NULL WHERE id = 2")
    # Act
    history = history_of(db, "Doe Jane")
    summary = summarise(history, Characteristic.AVERAGE_HEART_RATE)
    # Assert
    assert [row[Characteristic.AVERAGE_HEART_RATE] for _, row in history] == [70, None, 80]
    assert summary == Summary(2, 70, 80, 75, 70, 80, 10)
    assert history[0][1][Characteristic.AGE] == 40  # demographics come from astronauts


def test_all_none_values_give_empty_summary(tmp_path):
    db = make_db(tmp_path / "h.db", [70, 71])
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE measurement_history SET glucose = NULL")
    summary = summarise(history_of(db, "Doe Jane"), Characteristic.BLOOD_GLUCOSE)
    assert summary.count == 0 and summary.mean is None


def test_name_lookup_is_case_insensitive_and_missing_returns_none(tmp_path):
    db = make_db(tmp_path / "h.db", [60])
    assert astronaut_id(db, "doe JANE") is not None
    assert astronaut_id(db, "Doe") is None
    assert astronaut_id(db, "Smith John") is None
    assert astronaut_id(db, "x' OR '1'='1") is None


def test_missing_astronaut_prints_clear_message(tmp_path, capsys):
    db = make_db(tmp_path / "h.db", [60])
    code = main(["Smith John", "--db", str(db)])
    assert code == 1
    assert "Astronaut not found: Smith John" in capsys.readouterr().out


def test_missing_database_prints_message_and_creates_nothing(tmp_path, capsys):
    db = tmp_path / "absent.db"
    code = main(["Doe Jane", "--db", str(db)])
    assert code == 1
    assert "not found" in capsys.readouterr().out
    assert not db.exists()


def test_read_only_connection_rejects_writes(tmp_path):
    db = make_db(tmp_path / "h.db", [60])
    with closing(connect_read_only(db)) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM measurement_history")


def test_unknown_characteristic_is_rejected(tmp_path, capsys):
    db = make_db(tmp_path / "h.db", [60])
    assert parse_characteristic("not_a_thing") is None
    assert parse_characteristic(" blood_glucose ") is Characteristic.BLOOD_GLUCOSE
    code = main(["Doe Jane", "--characteristic", "not_a_thing", "--db", str(db)])
    assert code == 1
    assert "Unknown characteristic: not_a_thing" in capsys.readouterr().out


def test_cli_prints_summary_for_one_characteristic(tmp_path, capsys):
    db = make_db(tmp_path / "h.db", [60, 66])
    code = main(["Doe Jane", "--characteristic", "AVERAGE_HEART_RATE", "--db", str(db)])
    out = capsys.readouterr().out
    assert code == 0
    assert "2 measurement(s)" in out
    assert "Average heart rate (bpm): n=2 min=60 max=66 mean=63.00" in out
    assert "change=+6" in out
    assert "Blood glucose" not in out


def test_cli_lists_every_characteristic(tmp_path, capsys):
    db = make_db(tmp_path / "h.db", [60])
    assert main(["Doe Jane", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Age (years): n=1" in out
    assert out.count("\n") == 2 + 14


def test_age_weight_height_keep_a_history_per_save(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db")
    with closing(sqlite3.connect(db)) as conn:
        for weight in (75, 72):
            save_astronaut(conn, "Doe", "Jane", {**BASE_VALUES, Characteristic.BODY_WEIGHT: weight})

    # Act
    summary = summarise(history_of(db, "Doe Jane"), Characteristic.BODY_WEIGHT)

    # Assert
    assert (summary.first, summary.last, summary.change) == (75, 72, -3)


OLD_HISTORY_TABLE = (
    "CREATE TABLE measurement_history (id INTEGER PRIMARY KEY, astronaut_id INTEGER, "
    "recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, average_pulse REAL, "
    "systolic_pressure REAL, diastolic_pressure REAL, bmi REAL, glucose REAL, "
    "sleep_hours REAL, stress_level REAL, muscle_mass_percentage REAL, "
    "body_fat_percentage REAL, radiation_levels REAL, bone_density REAL)"
)


def test_create_table_adds_history_columns_to_an_old_database(tmp_path):
    # Arrange: measurement_history as it was before age/weight/height were kept
    db = tmp_path / "old.db"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(
            "CREATE TABLE astronauts (id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT NOT NULL, "
            "last_name TEXT NOT NULL, age INTEGER, height REAL, weight REAL, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE (first_name, last_name))"
        )
        conn.execute(OLD_HISTORY_TABLE)
        conn.execute("INSERT INTO astronauts (id, first_name, last_name) VALUES (1, 'Jane', 'Doe')")
        conn.execute("INSERT INTO measurement_history (astronaut_id, average_pulse) VALUES (1, 61)")
    before = summarise(history_of(db, "Doe Jane"), Characteristic.BODY_WEIGHT)

    # Act
    with closing(sqlite3.connect(db)) as conn:
        create_table(conn)
        save_astronaut(conn, "Doe", "Jane", BASE_VALUES)
    after = summarise(history_of(db, "Doe Jane"), Characteristic.BODY_WEIGHT)

    # Assert: old rows have no value, the new row has one, nothing crashed on the old schema
    assert before.count == 0
    assert (after.count, after.last) == (1, 75)


def test_printed_names_strip_control_characters(tmp_path, capsys):
    db = make_db(tmp_path / "h.db")
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO astronauts (first_name, last_name) VALUES ('Jane', 'Doe\x07')")
    main(["Doe\x07 Jane", "--db", str(db)])
    main(["Evil\x1b[2J Name", "--db", str(db)])
    out = capsys.readouterr().out
    assert "\x07" not in out and "\x1b" not in out
    assert "History for Doe Jane: 0 measurement(s)" in out
    assert "Astronaut not found: Evil[2J Name" in out
