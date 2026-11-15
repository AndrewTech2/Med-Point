import json
import sqlite3
from contextlib import closing

from Caracteristici import Characteristic
from calculations import connect_read_only
from export_history import build_export, main
from test_historic import make_db

PREFIX = "window.MED_POINT_HISTORY = "


def read_export(out):
    text = out.read_text(encoding="utf-8")
    assert text.startswith(PREFIX) and text.endswith(";\n")
    return json.loads(text[len(PREFIX):-2])


def test_export_has_points_and_summary_per_characteristic(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 66])

    # Act
    with closing(connect_read_only(db)) as conn:
        data = build_export(conn)

    # Assert
    jane = next(a for a in data["astronauts"] if a["name"] == "Jane Doe")
    heart = jane["metrics"][Characteristic.AVERAGE_HEART_RATE.name]
    assert [value for _, value in heart["points"]] == [60, 66]
    assert (heart["unit"], heart["summary"]["change"]) == ("bpm", 6)


def test_every_astronaut_has_the_integer_id_from_the_database(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 66])

    # Act
    with closing(connect_read_only(db)) as conn:
        data = build_export(conn)
        expected = [row[0] for row in conn.execute("SELECT id FROM astronauts ORDER BY id")]

    # Assert
    ids = [a["id"] for a in data["astronauts"]]
    assert all(type(i) is int for i in ids)
    assert ids == expected


def test_astronaut_without_measurements_has_no_metrics(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db", [60])

    # Act
    with closing(connect_read_only(db)) as conn:
        data = build_export(conn)

    # Assert
    nobody = next(a for a in data["astronauts"] if a["name"] == "Empty Nobody")
    assert nobody["metrics"] == {}


def test_main_writes_a_script_file_the_page_can_load(tmp_path, capsys):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 66])
    out = tmp_path / "health_history.js"

    # Act
    code = main(["--db", str(db), "--out", str(out)])

    # Assert
    assert code == 0
    assert len(read_export(out)["astronauts"]) == 2
    assert "Wrote 2 astronaut(s)" in capsys.readouterr().out


def test_missing_database_writes_nothing(tmp_path, capsys):
    # Arrange
    out = tmp_path / "health_history.js"

    # Act
    code = main(["--db", str(tmp_path / "none.db"), "--out", str(out)])

    # Assert
    assert code == 1 and not out.exists()
    assert "not found" in capsys.readouterr().out


def test_each_astronaut_embeds_the_recommendations_payload(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 66])

    # Act
    with closing(connect_read_only(db)) as conn:
        data = build_export(conn)

    # Assert
    for astronaut in data["astronauts"]:
        payload = astronaut["recommendations"]
        assert payload["astronaut_id"] == astronaut["id"]
        assert isinstance(payload["recommendations"], list)


def test_export_includes_vo2_and_recovery_and_skips_null_rows(tmp_path):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 66])
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("UPDATE measurement_history SET vo2_max = 44.5, hr_recovery = 25 WHERE id = 2")
        conn.commit()

    # Act
    with closing(connect_read_only(db)) as conn:
        data = build_export(conn)

    # Assert
    jane = next(a for a in data["astronauts"] if a["name"] == "Jane Doe")
    vo2 = jane["metrics"]["VO2_MAX"]
    assert [value for _, value in vo2["points"]] == [44.5]
    assert (vo2["unit"], vo2["label"]) == ("mL/kg/min", "VO2max")
    assert jane["metrics"]["HEART_RATE_RECOVERY"]["summary"]["last"] == 25
    nobody = next(a for a in data["astronauts"] if a["name"] == "Empty Nobody")
    assert "VO2_MAX" not in nobody["metrics"]
