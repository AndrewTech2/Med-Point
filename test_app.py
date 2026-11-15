import sqlite3

import pytest

from app import app
from test_historic import make_db

# make_db inserts the empty astronaut first, so Doe Jane gets id 2.
JANE_ID = 2


def test_dashboard_shows_average_heart_rate_with_one_decimal(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 61, 63])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    # Act
    response = client.get(f"/?astronaut_id={JANE_ID}")

    # Assert
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "61.3 BPM" in html
    assert "61.3333" not in html


def test_non_integer_astronaut_id_returns_400(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    # Act
    response = client.get("/?astronaut_id=abc")

    # Assert
    assert response.status_code == 400


def test_unknown_astronaut_id_returns_404(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    # Act
    response = client.get("/?astronaut_id=999")

    # Assert
    assert response.status_code == 404


def test_dashboard_loads_when_only_empty_astronaut_exists(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    # Act
    response = client.get("/")

    # Assert
    assert response.status_code == 200


def test_dashboard_all_null_pulses_show_dash(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [None, None])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    # Act
    response = client.get(f"/?astronaut_id={JANE_ID}")

    # Assert
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '<strong id="avgHrValue">—</strong>' in html


def test_dashboard_closes_connection_on_every_path(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    opened = []
    real_connect = sqlite3.connect

    def recording_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr("app.sqlite3.connect", recording_connect)
    client = app.test_client()

    # Act
    for url in ("/", "/?astronaut_id=abc", "/?astronaut_id=999"):
        client.get(url)

    # Assert
    assert len(opened) == 3
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("select 1")


@pytest.fixture
def interface_dir(tmp_path, monkeypatch):
    # Arrange: a small fake interface folder so asset tests do not depend on the real 18 MB model
    (tmp_path / "model.glb").write_bytes(b"glTF" + b"\0" * 16)
    (tmp_path / "script.js").write_text("console.log(1);", encoding="utf-8")
    monkeypatch.setattr("app.INTERFACE_DIR", tmp_path)
    return tmp_path


def test_glb_asset_is_cached_for_a_day(interface_dir):
    # Arrange
    client = app.test_client()

    # Act
    response = client.get("/model.glb")

    # Assert
    assert response.status_code == 200
    assert "max-age=86400" in response.headers["Cache-Control"]


def test_js_asset_revalidates_and_returns_304_on_match(interface_dir):
    # Arrange
    client = app.test_client()
    first = client.get("/script.js")
    etag = first.headers["ETag"]

    # Act
    response = client.get("/script.js", headers={"If-None-Match": etag})

    # Assert
    assert first.headers["Cache-Control"] == "no-cache"
    assert response.status_code == 304


def test_dashboard_shows_latest_vo2_and_recovery_instead_of_dash(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 61])
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE measurement_history SET vo2_max = 44.5, hr_recovery = 25 WHERE id = 1")
        conn.execute("UPDATE measurement_history SET vo2_max = 43.2, hr_recovery = 24 WHERE id = 2")
        conn.execute("UPDATE measurement_history SET hr_recovery = NULL WHERE id = 2")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    # Act
    html = app.test_client().get(f"/?astronaut_id={JANE_ID}").get_data(as_text=True)

    # Assert: the newest non-null value of each metric
    assert '<strong id="summaryVo2Value">43.2 mL/kg/min</strong>' in html
    assert '<strong id="recoveryValue">25 bpm</strong>' in html


def test_dashboard_shows_dash_for_vo2_and_recovery_without_data(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    html = app.test_client().get(f"/?astronaut_id={JANE_ID}").get_data(as_text=True)
    assert '<strong id="recoveryValue">—</strong>' in html
    assert '<strong id="summaryVo2Value">—</strong>' in html
