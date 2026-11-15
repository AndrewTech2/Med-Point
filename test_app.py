import sqlite3

import pytest

from app import app
from test_historic import make_db
from werkzeug.security import check_password_hash, generate_password_hash

# make_db inserts the empty astronaut first, so Doe Jane gets id 2.
JANE_ID = 2


def _authenticated_client(client, astronaut_id=None):
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["astronaut_id"] = JANE_ID if astronaut_id is None else astronaut_id
    return client


def test_dashboard_redirects_unauthenticated_users_to_login():
    response = app.test_client().get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_dashboard_shows_average_heart_rate_with_one_decimal(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60, 61, 63])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client())

    # Act
    response = client.get(f"/?astronaut_id={JANE_ID}")

    # Assert
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "61.3 BPM" in html
    assert "61.3333" not in html


def test_dashboard_explains_when_no_astronaut_data_has_been_collected(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM astronauts")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    response = _authenticated_client(app.test_client()).get("/")

    assert response.status_code == 200
    assert b"No astronaut data has been collected yet." in response.data
    assert b"No data has been collected yet." in response.data


def test_non_integer_astronaut_id_returns_400(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client())

    # Act
    response = client.get("/?astronaut_id=abc")

    # Assert
    assert response.status_code == 400


def test_unknown_astronaut_id_returns_404(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client())

    # Act
    response = client.get("/?astronaut_id=999")

    # Assert
    assert response.status_code == 404


def test_dashboard_loads_when_only_empty_astronaut_exists(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client(), astronaut_id=1)

    # Act
    response = client.get("/", follow_redirects=True)

    # Assert
    assert response.status_code == 200


def test_login_finds_legacy_user_astronaut_when_account_row_is_unlinked(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db", [60])
    with sqlite3.connect(db) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS user_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                height_cm REAL NOT NULL,
                weight_kg REAL NOT NULL,
                astronaut_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute("ALTER TABLE astronauts ADD COLUMN crew TEXT")
        conn.execute("UPDATE astronauts SET crew = 'Alpha'")
        conn.execute(
            """INSERT INTO user_accounts
               (email, password_hash, full_name, age, height_cm, weight_kg, astronaut_id)
               VALUES (?, ?, ?, ?, ?, ?, NULL)""",
            (
                "doe.jane@example.test",
                generate_password_hash("secure-passphrase"),
                "Doe Jane",
                35,
                170.0,
                65.0,
            ),
        )
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    response = client.post(
        "/login",
        data={"email": "doe.jane@example.test", "password": "secure-passphrase"},
    )
    dashboard = client.get("/", follow_redirects=True)

    assert response.status_code == 302
    assert response.headers["Location"] == "/?astronaut_id=2"
    assert dashboard.status_code == 200
    assert b'class="crew-card"' in dashboard.data
    assert b"Jane Doe" in dashboard.data
    with client.session_transaction() as session:
        assert session["astronaut_id"] == 2


def test_dashboard_all_null_pulses_show_dash(tmp_path, monkeypatch):
    # Arrange
    db = make_db(tmp_path / "h.db", [None, None])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client())

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
    client = _authenticated_client(app.test_client())

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
    client = _authenticated_client(app.test_client())
    html = client.get(f"/?astronaut_id={JANE_ID}").get_data(as_text=True)

    # Assert: the newest non-null value of each metric
    assert '<strong id="summaryVo2Value">43.2 mL/kg/min</strong>' in html
    assert '<strong id="recoveryValue">25 bpm</strong>' in html


def test_dashboard_shows_dash_for_vo2_and_recovery_without_data(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db", [60])
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client())
    html = client.get(f"/?astronaut_id={JANE_ID}").get_data(as_text=True)
    assert '<strong id="recoveryValue">—</strong>' in html
    assert '<strong id="summaryVo2Value">—</strong>' in html


def _signup_data(**overrides):
    return {
        "full_name": "Alex Morgan",
        "email": "alex@example.org",
        "password": "secure-passphrase",
        "age": "34",
        "height_cm": "172.5",
        "weight_kg": "68.2",
        "crew": "Crew 1",
        **overrides,
    }


def test_signup_and_login_pages_link_to_each_other(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    signup_response = client.get("/signup")
    login_response = client.get("/login")

    assert signup_response.status_code == 200
    signup_html = signup_response.get_data(as_text=True)
    assert 'name="full_name"' in signup_html
    assert 'name="age"' in signup_html
    assert 'name="height_cm"' in signup_html
    assert 'name="weight_kg"' in signup_html
    assert 'name="crew"' in signup_html
    assert "new name to form one" in signup_html
    assert "Crew 1" in signup_html
    assert 'href="/login"' in signup_html
    assert 'href="/signup"' in login_response.get_data(as_text=True)


def test_signup_persists_profile_and_password_hash(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    response = app.test_client().post("/signup", data=_signup_data(), follow_redirects=True)

    assert response.status_code == 200
    assert b"Your account is ready" in response.data
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            """SELECT email, password_hash, full_name, age, height_cm, weight_kg, astronaut_id
               FROM user_accounts"""
        ).fetchone()
    assert row[0] == "alex@example.org"
    assert check_password_hash(row[1], "secure-passphrase")
    assert row[1] != "secure-passphrase"
    assert row[2:] == ("Alex Morgan", 34, 172.5, 68.2, 2)
    with sqlite3.connect(db) as conn:
        astronaut = conn.execute(
            """SELECT first_name, last_name, age, height, weight, crew
               FROM astronauts WHERE id = ?""",
            (row[6],),
        ).fetchone()
    assert astronaut == ("Alex", "Morgan", 34, 172.5, 68.2, "Crew 1")


def test_login_authenticates_and_uses_assigned_astronaut(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()
    client.post("/signup", data=_signup_data())

    response = client.post(
        "/login",
        data={"email": "ALEX@example.org", "password": "secure-passphrase"},
    )
    dashboard = client.get(response.headers["Location"])

    assert response.status_code == 302
    assert response.headers["Location"] == "/?astronaut_id=2"
    assert dashboard.request.path == "/"
    assert dashboard.request.args["astronaut_id"] == "2"
    assert dashboard.status_code == 200
    assert b"Alex Morgan" in dashboard.data
    assert b"Empty Nobody" in dashboard.data


def test_new_astronaut_gets_a_crew_overview_card(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE astronauts ADD COLUMN crew TEXT")
        conn.execute("UPDATE astronauts SET crew = 'Alpha'")
        conn.executemany(
            """INSERT INTO astronauts (first_name, last_name, crew)
               VALUES (?, ?, 'Alpha')""",
            [("Kai", "Orion"), ("Nova", "Sirius"), ("Lynx", "Ara")],
        )
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()
    client.post("/signup", data=_signup_data(crew="Alpha"))
    client.post(
        "/login",
        data={"email": "alex@example.org", "password": "secure-passphrase"},
    )

    dashboard = client.get("/?astronaut_id=5")

    assert dashboard.status_code == 200
    assert dashboard.data.count(b'class="crew-card"') == 5
    assert b'data-astronaut-id="5"' in dashboard.data
    assert b'data-astronaut-name="Alex Morgan"' in dashboard.data
    assert b">05</span>" in dashboard.data


def test_dashboard_only_shows_astronauts_from_the_authenticated_crew(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE astronauts ADD COLUMN crew TEXT")
        conn.execute("UPDATE astronauts SET crew = 'Alpha'")
        conn.execute(
            """INSERT INTO astronauts (first_name, last_name, crew)
               VALUES ('Beta', 'Crewmate', 'Beta')"""
        )
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()
    client.post("/signup", data=_signup_data(crew="Beta"))
    client.post(
        "/login",
        data={"email": "alex@example.org", "password": "secure-passphrase"},
    )

    dashboard = client.get("/", follow_redirects=True)

    assert dashboard.status_code == 200
    assert dashboard.data.count(b'class="crew-card"') == 2
    assert b"Beta Crewmate" in dashboard.data
    assert b"Alex Morgan" in dashboard.data
    assert b"Empty Nobody" not in dashboard.data
    assert client.get("/?astronaut_id=1").status_code == 404


def test_dashboard_without_assigned_astronaut_shows_no_crew_members(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db", [60])
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE astronauts ADD COLUMN crew TEXT")
        conn.execute("UPDATE astronauts SET crew = 'Alpha'")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1

    dashboard = client.get("/")

    assert dashboard.status_code == 200
    assert b'class="crew-card"' not in dashboard.data
    assert b"Doe Jane" not in dashboard.data


def test_login_reports_invalid_credentials_without_server_error(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()
    client.post("/signup", data=_signup_data())

    response = client.post(
        "/login",
        data={"email": "alex@example.org", "password": "wrong-passphrase"},
    )

    assert response.status_code == 401
    assert b"Email or password is incorrect." in response.data


def test_logout_clears_authenticated_session(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()
    client.post("/signup", data=_signup_data())
    client.post(
        "/login",
        data={"email": "alex@example.org", "password": "secure-passphrase"},
    )

    dashboard = client.get("/?astronaut_id=1")
    response = client.post("/logout")
    after_logout = client.get("/?astronaut_id=1")

    assert b"Sign out" in dashboard.data
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert b"Sign out" not in after_logout.data


def test_daily_tasks_check_only_values_recorded_today(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    with sqlite3.connect(db) as conn:
        conn.execute(
            """INSERT INTO measurement_history (astronaut_id, recorded_at, average_pulse)
               VALUES (1, datetime('now'), 60)"""
        )
        conn.execute(
            """INSERT INTO measurement_history (astronaut_id, recorded_at, sleep_hours)
               VALUES (1, datetime('now', '-1 day'), 8)"""
        )
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = _authenticated_client(app.test_client())

    response = client.get("/api/astronauts/1/daily-tasks")

    assert response.status_code == 200
    tasks = {task["key"]: task for task in response.json["tasks"]}
    assert tasks["AVERAGE_HEART_RATE"]["checked"] is True
    assert tasks["SLEEP_HOURS"]["checked"] is False
    assert tasks["BODY_MASS_INDEX"]["checked"] is False
    assert tasks["VO2_MAX"]["checked"] is False


def test_daily_tasks_require_authentication(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    response = app.test_client().get("/api/astronauts/1/daily-tasks")

    assert response.status_code == 401
    assert response.json == {"error": "authentication required"}


def test_signup_can_form_a_new_crew_without_existing_crew_data(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM astronauts")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    response = app.test_client().post(
        "/signup", data=_signup_data(crew="Orion Explorers")
    )

    assert response.status_code == 302
    with sqlite3.connect(db) as conn:
        crew = conn.execute("SELECT crew FROM astronauts").fetchone()[0]
    assert crew == "Orion Explorers"


def test_signup_without_available_astronauts_explains_no_data(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM astronauts")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    response = app.test_client().get("/signup")

    assert response.status_code == 200
    assert b"No astronaut data has been collected yet" in response.data


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", "-1"),
        ("height_cm", "nan"),
        ("weight_kg", "0"),
        ("full_name", "   "),
        ("password", "short"),
        ("crew", "Invalid\x07 crew"),
    ],
)
def test_signup_rejects_invalid_required_values(tmp_path, monkeypatch, field, value):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)

    response = app.test_client().post("/signup", data=_signup_data(**{field: value}))

    assert response.status_code == 400
    with sqlite3.connect(db) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_accounts'"
        ).fetchone()
    assert tables is None


def test_signup_rejects_duplicate_email(tmp_path, monkeypatch):
    db = make_db(tmp_path / "h.db")
    monkeypatch.setattr("app.DATABASE_PATH", db)
    client = app.test_client()

    first = client.post("/signup", data=_signup_data())
    duplicate = client.post("/signup", data=_signup_data(full_name="Another Person"))

    assert first.status_code == 302
    assert duplicate.status_code == 409
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM user_accounts").fetchone()[0]
    assert count == 1
