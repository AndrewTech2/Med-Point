import sqlite3
from collections.abc import Mapping
from contextlib import closing

import pytest

from Caracteristici import Characteristic, create_table, save_astronaut
from app import app
from calculations import connect_read_only
from dashboard_terminal import DISCLAIMER
from recommendation_types import BodySystem, MissionPhase, Status
from recommendations import Assessment, Recommendation, SystemStatus
from recommendations_api import (
    build_payload,
    load_latest,
    payload_for_astronaut,
    recommendation_to_dict,
    region_scores,
)
from test_historic import BASE_VALUES, make_db

JANE_ID = 2
NOBODY_ID = 1
MISSING_ID = 999
TOP_LEVEL_KEYS = {
    "astronaut_id",
    "name",
    "recorded_at",
    "phase",
    "overall",
    "overall_level",
    "multi_system_review",
    "recommendations",
    "regions",
    "measure_this",
    "disclaimer",
}
RECOMMENDATION_KEYS = {
    "action",
    "status",
    "level",
    "rule_ids",
    "rules",
    "systems",
    "metrics",
    "body_regions",
    "sources",
    "phase_relevant",
}
REGION_NAMES = {"head", "torso", "arms", "legs"}
LEVEL_BY_STATUS = {"UNKNOWN": -1, "OK": 0, "WATCH": 1, "ACTION": 2, "URGENT": 3}


def make_client(tmp_path, monkeypatch, extra_rows: Mapping[str, Mapping] = {}):
    """Build the demo DB (Jane = id 2 with a BASE_VALUES measurement), add extra rows, point the app at it."""
    db = make_db(tmp_path / "api.db", [BASE_VALUES[Characteristic.AVERAGE_HEART_RATE]])
    with closing(sqlite3.connect(db)) as conn:
        create_table(conn)
        for values in extra_rows.values():
            save_astronaut(conn, "Doe", "Jane", {**BASE_VALUES, **values})
        conn.commit()
    monkeypatch.setattr("app.DATABASE_PATH", db)
    return app.test_client()


def get_json(client, path: str):
    response = client.get(path)
    return response, response.get_json()


def test_jane_response_has_contract_keys_and_types(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    response, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations")

    # Assert
    assert response.status_code == 200
    assert response.is_json
    assert set(data) == TOP_LEVEL_KEYS
    assert data["astronaut_id"] == JANE_ID
    assert data["name"] == "Doe Jane"
    assert isinstance(data["recorded_at"], str)
    assert data["phase"] == "unknown"
    assert data["overall"] in LEVEL_BY_STATUS
    assert isinstance(data["overall_level"], int)
    assert isinstance(data["multi_system_review"], bool)
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["measure_this"], list)
    assert data["disclaimer"] == DISCLAIMER


def test_each_recommendation_has_contract_keys_and_types(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch, {"glucose": {Characteristic.BLOOD_GLUCOSE: 50}})

    # Act
    _, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations")

    # Assert
    assert data["recommendations"]
    for item in data["recommendations"]:
        assert set(item) == RECOMMENDATION_KEYS
        assert isinstance(item["action"], str) and item["action"]
        assert item["level"] == LEVEL_BY_STATUS[item["status"]]
        assert all(set(rule) == {"id", "variable", "condition"} for rule in item["rules"])
        assert isinstance(item["phase_relevant"], bool)


def test_glucose_50_gives_urgent_recommendation_with_glucose_metric(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch, {"glucose": {Characteristic.BLOOD_GLUCOSE: 50}})

    # Act
    _, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations")

    # Assert
    assert data["overall"] == "URGENT"
    assert data["overall_level"] == 3
    urgent = [item for item in data["recommendations"] if item["status"] == "URGENT"]
    assert urgent
    assert any("BLOOD_GLUCOSE" in item["metrics"] for item in urgent)
    assert all(item["body_regions"] for item in data["recommendations"])


def test_recommendations_are_sorted_by_level_descending(tmp_path, monkeypatch):
    # Arrange
    client = make_client(
        tmp_path,
        monkeypatch,
        {
            "glucose": {Characteristic.BLOOD_GLUCOSE: 50},
            "pressure": {Characteristic.SYSTOLIC_BLOOD_PRESSURE: 150},
        },
    )

    # Act
    _, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations")

    # Assert
    levels = [item["level"] for item in data["recommendations"]]
    assert len(levels) >= 2
    assert levels == sorted(levels, reverse=True)


def test_region_values_are_ints_between_0_and_100(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch, {"glucose": {Characteristic.BLOOD_GLUCOSE: 50}})

    # Act
    _, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations")

    # Assert
    regions = data["regions"]
    assert regions
    assert set(regions) <= REGION_NAMES
    for score in regions.values():
        assert isinstance(score, int)
        assert 0 <= score <= 100


def test_healthy_base_values_give_no_recommendation_at_level_2_or_higher(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    _, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations")

    # Assert
    assert all(item["level"] < 2 for item in data["recommendations"])


def test_astronaut_without_measurements_has_null_recorded_at(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    response, data = get_json(client, f"/api/astronauts/{NOBODY_ID}/recommendations")

    # Assert
    assert response.status_code == 200
    assert data["name"] == "Nobody Empty"
    assert data["recorded_at"] is None
    assert data["overall"] == "UNKNOWN"


def test_unknown_astronaut_returns_404_json_error(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    response, data = get_json(client, f"/api/astronauts/{MISSING_ID}/recommendations")

    # Assert
    assert response.status_code == 404
    assert response.is_json
    assert data == {"error": "astronaut not found"}


@pytest.mark.parametrize("phase", ["", "sleep", "RETURN", "return-phase"])
def test_invalid_phase_returns_400_json_error(tmp_path, monkeypatch, phase):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    response, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations?phase={phase}")

    # Assert
    assert response.status_code == 400
    assert response.is_json
    assert "error" in data


def test_return_phase_is_echoed_in_payload(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    response, data = get_json(client, f"/api/astronauts/{JANE_ID}/recommendations?phase=return")

    # Assert
    assert response.status_code == 200
    assert data["phase"] == "return"


def test_asset_route_still_404s_for_python_source_and_root_still_200(tmp_path, monkeypatch):
    # Arrange
    client = make_client(tmp_path, monkeypatch)

    # Act
    py_response = client.get("/app.py")
    root_response = client.get("/")

    # Assert
    assert py_response.status_code == 404
    assert root_response.status_code == 200


def test_load_latest_returns_none_for_missing_id(tmp_path):
    # Arrange
    db = make_db(tmp_path / "api.db")

    # Act
    with closing(connect_read_only(db)) as conn:
        loaded = load_latest(conn, MISSING_ID)

    # Assert
    assert loaded is None


def test_load_latest_reads_demographics_and_latest_measurement(tmp_path):
    # Arrange
    db = make_db(tmp_path / "api.db", [64])

    # Act
    with closing(connect_read_only(db)) as conn:
        name, recorded_at, values = load_latest(conn, JANE_ID)

    # Assert
    assert name == "Doe Jane"
    assert recorded_at is not None
    assert values[Characteristic.AVERAGE_HEART_RATE] == 64
    assert values[Characteristic.AGE] == BASE_VALUES[Characteristic.AGE]
    assert values[Characteristic.HEIGHT] == BASE_VALUES[Characteristic.HEIGHT]


def test_payload_for_astronaut_returns_none_for_missing_id(tmp_path):
    # Arrange
    db = make_db(tmp_path / "api.db")

    # Act
    with closing(connect_read_only(db)) as conn:
        payload = payload_for_astronaut(conn, MISSING_ID)

    # Assert
    assert payload is None


def _system(system: BodySystem, status: Status) -> SystemStatus:
    return SystemStatus(system=system, status=status, rule_ids=())


def _assessment(systems: tuple[SystemStatus, ...]) -> Assessment:
    return Assessment(
        phase=MissionPhase.UNKNOWN,
        overall=Status.UNKNOWN,
        multi_system_review=False,
        systems=systems,
        results=(),
        recommendations=(),
        measure_this=(),
        invalid_inputs=(),
        provided=frozenset(),
    )


def test_region_scores_use_worst_known_system_per_region():
    # Arrange
    assessment = _assessment(
        (
            _system(BodySystem.HEART_VESSELS, Status.WATCH),
            _system(BodySystem.BLOOD, Status.ACTION),
            _system(BodySystem.BRAIN, Status.OK),
            _system(BodySystem.EYES, Status.UNKNOWN),
            _system(BodySystem.SLEEP, Status.UNKNOWN),
            _system(BodySystem.MUSCLES, Status.OK),
            _system(BodySystem.BONES, Status.UNKNOWN),
        )
    )

    # Act
    scores = region_scores(assessment)

    # Assert
    assert scores == {"head": 100, "torso": 45, "arms": 100}


def test_region_scores_omit_region_when_all_systems_unknown_and_map_urgent_to_15():
    # Arrange
    assessment = _assessment(
        (
            _system(BodySystem.BONES, Status.URGENT),
            _system(BodySystem.BRAIN, Status.UNKNOWN),
        )
    )

    # Act
    scores = region_scores(assessment)

    # Assert
    assert scores == {"legs": 15}


def test_recommendation_to_dict_maps_rules_metrics_regions_and_sources():
    # Arrange
    recommendation = Recommendation(
        action="Test action",
        status=Status.ACTION,
        rule_ids=("CV-3",),
        systems=(BodySystem.HEART_VESSELS,),
        sources=("[S14, S15]",),
        phase_relevant=False,
    )

    # Act
    item = recommendation_to_dict(recommendation)

    # Assert
    assert set(item) == RECOMMENDATION_KEYS
    assert item["status"] == "ACTION"
    assert item["level"] == 2
    assert item["rule_ids"] == ["CV-3"]
    assert [rule["id"] for rule in item["rules"]] == ["CV-3"]
    assert item["systems"] == ["Heart & vessels"]
    assert item["metrics"] == ["SYSTOLIC_BLOOD_PRESSURE", "DIASTOLIC_BLOOD_PRESSURE"]
    assert item["body_regions"] == ["torso"]
    assert item["sources"] == ["[S14, S15]"]
    assert item["phase_relevant"] is False


def test_build_payload_does_not_mutate_input_values():
    # Arrange
    values = {Characteristic.BLOOD_GLUCOSE: 50}
    snapshot = dict(values)

    # Act
    payload = build_payload(JANE_ID, "Doe Jane", None, values)

    # Assert
    assert values == snapshot
    assert payload["overall"] == "URGENT"
    assert payload["recorded_at"] is None
    assert payload["measure_this"]
