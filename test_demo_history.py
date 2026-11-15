import sqlite3
import statistics
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from Caracteristici import (
    CHARACTERISTIC_DEFINITIONS,
    Characteristic,
    check_consistency,
    create_table,
    is_within_limits,
)
from calculations import connect_read_only, load_astronauts
from demo_history import (
    DEMO_PROFILES,
    END,
    MISSION_START,
    TIMESTAMP_FORMAT,
    generate_history,
    main,
    seed_database,
)
from historic import find_astronaut_id, list_history
from recommendation_types import Status
from recommendations import assess
from test_historic import make_db

VEGA, ORION, NOVA, LYNX = DEMO_PROFILES


def _history(profile, end=END):
    return generate_history(profile, end)


def _times(history) -> list[datetime]:
    return [datetime.strptime(recorded_at, TIMESTAMP_FORMAT) for recorded_at, _ in history]


def _series(history, characteristic: Characteristic) -> list[float]:
    return [values[characteristic] for _, values in history]


def _seeded_db(tmp_path: Path, name: str = "demo.db") -> Path:
    db = tmp_path / name
    with closing(sqlite3.connect(db)) as conn:
        seed_database(conn)
    return db


def test_generate_history_is_deterministic():
    # Arrange / Act
    first = _history(VEGA)
    second = _history(VEGA)
    # Assert
    assert first == second


def test_astronauts_have_different_histories():
    assert _history(VEGA) != _history(ORION)
    assert _series(_history(VEGA), Characteristic.AVERAGE_HEART_RATE) != _series(
        _history(NOVA), Characteristic.AVERAGE_HEART_RATE
    )


def test_rows_are_sorted_with_unique_timestamps_and_all_characteristics():
    # Arrange
    history = _history(NOVA)
    times = _times(history)
    # Assert
    assert times == sorted(times)
    assert len(set(times)) == len(times)
    expected_keys = set(Characteristic)
    assert all(set(values) == expected_keys for _, values in history)


def test_every_row_is_within_limits_and_consistent():
    for profile in DEMO_PROFILES:
        for _, values in _history(profile):
            for definition in CHARACTERISTIC_DEFINITIONS:
                assert is_within_limits(definition, values[definition.characteristic])
            assert check_consistency(dict(values)) == []


def test_recent_hours_have_readings_every_three_hours():
    times = _times(_history(VEGA))
    recent = [t for t in times if t >= END - timedelta(hours=24)]
    assert len(recent) >= 8


def test_readings_cover_five_distinct_days_in_last_five_days():
    times = _times(_history(VEGA))
    recent_days = {t.date() for t in times if t >= END - timedelta(days=5)}
    assert len(recent_days) >= 5


def test_history_reaches_back_more_than_five_years():
    earliest = min(_times(_history(VEGA)))
    assert earliest <= END - timedelta(days=5 * 365)


def test_heart_rate_varies_over_the_last_thirty_days():
    history = _history(VEGA)
    recent = [
        values[Characteristic.AVERAGE_HEART_RATE]
        for t, (_, values) in zip(_times(history), history)
        if t >= END - timedelta(days=30)
    ]
    assert statistics.stdev(recent) > 1


def test_nova_bone_density_is_lower_at_the_end_than_at_mission_start():
    history = _history(NOVA)
    bone = dict(zip(_times(history), _series(history, Characteristic.BONE_DENSITY_CALCIUM)))
    at_start = next(value for t, value in bone.items() if t >= MISSION_START)
    at_end = bone[max(bone)]
    assert at_end < at_start


def test_radiation_at_the_end_exceeds_the_level_before_the_mission():
    history = _history(VEGA)
    radiation = dict(zip(_times(history), _series(history, Characteristic.MISSION_RADIATION_LEVEL)))
    before = max(value for t, value in radiation.items() if t < MISSION_START)
    assert radiation[max(radiation)] > before


def test_seed_database_keeps_other_astronauts_unchanged(tmp_path):
    # Arrange
    db = make_db(tmp_path / "other.db", [60, 62])
    with closing(connect_read_only(db)) as conn:
        doe_id = find_astronaut_id(conn, "Doe Jane")
    before = _measurement_rows(db, doe_id)
    # Act
    with closing(sqlite3.connect(db)) as conn:
        counts = seed_database(conn)
    # Assert
    assert _measurement_rows(db, doe_id) == before
    assert set(counts) == {"Lyra Vega", "Orion Kai", "Sirius Nova", "Ara Lynx"}


def _measurement_rows(db: Path, astronaut_id: int) -> list[tuple]:
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute(
            "SELECT * FROM measurement_history WHERE astronaut_id = ? ORDER BY id",
            (astronaut_id,),
        ).fetchall()


def test_seed_database_is_idempotent(tmp_path):
    db = tmp_path / "demo.db"
    with closing(sqlite3.connect(db)) as conn:
        first = seed_database(conn)
    with closing(sqlite3.connect(db)) as conn:
        second = seed_database(conn)
        total = conn.execute("SELECT COUNT(*) FROM measurement_history").fetchone()[0]
        astronauts = conn.execute("SELECT COUNT(*) FROM astronauts").fetchone()[0]
    assert first == second
    assert total == sum(first.values())
    assert astronauts == len(DEMO_PROFILES)


def test_seeded_astronauts_have_all_fourteen_characteristics_in_history(tmp_path):
    db = _seeded_db(tmp_path)
    with closing(connect_read_only(db)) as conn:
        astronaut_id = find_astronaut_id(conn, "Lyra Vega")
        history = list_history(conn, astronaut_id)
    last_values = history[-1][1]
    assert len(history) > 300
    assert all(value is not None for value in last_values.values())
    assert len(last_values) == 14


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Lyra Vega", Status.OK),
        ("Orion Kai", Status.ACTION),
        ("Sirius Nova", None),
        ("Ara Lynx", Status.URGENT),
    ],
)
def test_final_overall_statuses(tmp_path, name, expected):
    db = _seeded_db(tmp_path)
    with closing(connect_read_only(db)) as conn:
        astronauts = load_astronauts(conn)
    last, first = name.split()[0], name.split()[1]
    assessment = assess(astronauts[(last, first)])
    if expected is None:
        assert assessment.overall in (Status.WATCH, Status.ACTION)
    else:
        assert assessment.overall is expected


def test_main_writes_one_summary_line_per_astronaut(tmp_path, capsys):
    db = tmp_path / "cli.db"
    code = main(["--db", str(db)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert code == 0
    assert len(lines) == len(DEMO_PROFILES)
    assert all("rows written" in line for line in lines)


def test_seed_database_creates_astronaut_time_index_and_is_rerunnable(tmp_path):
    db = tmp_path / "demo.db"
    with closing(sqlite3.connect(db)) as conn:
        seed_database(conn)
        seed_database(conn)
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(measurement_history)")}
        plan = " ".join(
            str(row[3])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM measurement_history "
                "WHERE astronaut_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
                (1,),
            )
        )
    assert "idx_measurement_history_astronaut_time" in indexes
    assert "idx_measurement_history_astronaut_time" in plan
    assert "TEMP B-TREE" not in plan
    with closing(sqlite3.connect(db)) as conn:
        avg_plan = " ".join(
            str(row[3])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT AVG(average_pulse) FROM measurement_history "
                "WHERE astronaut_id = ?",
                (1,),
            )
        )
    assert "COVERING INDEX idx_measurement_history_astronaut_time" in avg_plan


# --- VO2max and heart-rate recovery (stored beside the 14 characteristics) ---------------
from Caracteristici import HISTORY_EXTRAS, extra_series  # noqa: E402
from demo_history import generate_extras  # noqa: E402

VO2, RECOVERY = HISTORY_EXTRAS


def _extra_values(profile, extra):
    return [values[extra.key] for _, values in generate_extras(profile)]


def test_extras_cover_every_history_row_and_are_deterministic():
    for profile in DEMO_PROFILES:
        extras = generate_extras(profile)
        assert [when for when, _ in extras] == [when for when, _ in _history(profile)]
        assert extras == generate_extras(profile)


@pytest.mark.parametrize("profile", DEMO_PROFILES, ids=lambda p: p.first_name)
def test_extras_stay_within_limits(profile):
    for extra in HISTORY_EXTRAS:
        values = _extra_values(profile, extra)
        assert all(extra.minimum <= v <= extra.maximum for v in values)


def test_vo2_declines_roughly_five_to_fifteen_percent_over_the_mission():
    for profile in DEMO_PROFILES:
        extras = dict(generate_extras(profile))
        series = [(datetime.strptime(w, TIMESTAMP_FORMAT), v[VO2.key]) for w, v in extras.items()]
        start = min(series, key=lambda s: abs(s[0] - MISSION_START))[1]
        end = series[-1][1]
        assert 0.84 <= end / start <= 0.96  # about -5..-15%, minus noise at the start reading


def test_recovery_is_healthy_and_lower_for_deconditioned_astronaut():
    finals = {p.first_name: _extra_values(p, RECOVERY)[-1] for p in DEMO_PROFILES}
    assert all(12 < v <= 35 for v in finals.values())
    assert finals["Nova"] < finals["Vega"]


def test_extras_differ_between_astronauts():
    finals = {_extra_values(p, VO2)[-1] for p in DEMO_PROFILES}
    assert len(finals) == len(DEMO_PROFILES)


def test_seed_database_stores_extras_and_is_idempotent(tmp_path):
    db = tmp_path / "demo.db"
    with closing(sqlite3.connect(db)) as conn:
        seed_database(conn)
        seed_database(conn)
        for index, profile in enumerate(DEMO_PROFILES, start=1):
            for extra in HISTORY_EXTRAS:
                stored = extra_series(conn, index, extra)
                assert [v for _, v in stored] == _extra_values(profile, extra)


def test_create_table_adds_extra_columns_to_old_database(tmp_path):
    db = tmp_path / "old.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE measurement_history (id INTEGER PRIMARY KEY, astronaut_id INTEGER, recorded_at TEXT)")
        assert extra_series(conn, 1, VO2) == []
        create_table(conn)
        create_table(conn)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(measurement_history)")}
    assert {VO2.column, RECOVERY.column} <= columns
