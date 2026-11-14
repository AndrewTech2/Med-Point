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
