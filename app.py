import math
import os
import re
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_session import Session
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from Caracteristici import (
    CHARACTERISTIC_COLUMNS,
    CHARACTERISTIC_DEFINITIONS,
    HISTORY_EXTRAS,
    extra_series,
)
from recommendation_types import MissionPhase
from recommendations_api import payload_for_astronaut


BASE_DIR = Path(__file__).resolve().parent
INTERFACE_DIR = BASE_DIR / "Med-Point-fixed" / "Med-Point Interface"
DATABASE_PATH = BASE_DIR / "astronauts.db"

app = Flask(
    __name__,
    template_folder=str(INTERFACE_DIR),
    static_folder=None,
)
app.config["SECRET_KEY"] = os.environ.get("MED_POINT_SECRET_KEY") or secrets.token_hex(32)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
Session(app)
ASSET_EXTENSIONS = {".css", ".glb", ".js"}
GLB_MAX_AGE_SECONDS = 24 * 60 * 60
DAILY_TASK_CHARACTERISTICS = tuple(
    (
        definition.characteristic.name,
        definition.characteristic.value,
        CHARACTERISTIC_COLUMNS[definition.characteristic],
    )
    for definition in CHARACTERISTIC_DEFINITIONS
) + tuple((extra.key, extra.label, extra.column) for extra in HISTORY_EXTRAS)

CREATE_USER_ACCOUNTS_TABLE = """
    CREATE TABLE IF NOT EXISTS user_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
        height_cm REAL NOT NULL CHECK (height_cm BETWEEN 50 AND 300),
        weight_kg REAL NOT NULL CHECK (weight_kg BETWEEN 1 AND 1000),
        astronaut_id INTEGER REFERENCES astronauts(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def _ensure_user_accounts_table(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_USER_ACCOUNTS_TABLE)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(user_accounts)")}
    if "astronaut_id" not in columns:
        conn.execute(
            "ALTER TABLE user_accounts ADD COLUMN astronaut_id INTEGER REFERENCES astronauts(id)"
        )


def _ensure_astronaut_crew_column(conn: sqlite3.Connection) -> None:
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if "astronauts" not in tables:
        return

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(astronauts)")}
    if "crew" not in columns:
        conn.execute("ALTER TABLE astronauts ADD COLUMN crew TEXT")
    conn.execute(
        "UPDATE astronauts SET crew = 'Crew 1' WHERE crew IS NULL OR TRIM(crew) = ''"
    )


def _available_crew(conn: sqlite3.Connection) -> list[str]:
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if "astronauts" not in tables:
        return []
    return [
        row["crew"]
        for row in conn.execute(
            """SELECT DISTINCT crew
               FROM astronauts
               WHERE crew IS NOT NULL AND TRIM(crew) != ''
               ORDER BY crew"""
        )
    ]


def _format_measurement(value: float | int | None, unit: str = "") -> str:
    if value is None:
        return "—"
    formatted = f"{value:g}"
    return f"{formatted} {unit}".strip()


@app.get("/<path:filename>")
def interface_asset(filename: str):
    suffix = Path(filename).suffix.lower()
    if suffix not in ASSET_EXTENSIONS:
        abort(404)
    if suffix == ".glb":
        # shortcut: a replaced model can show stale for up to a day, upgrade to fingerprinted filenames.
        return send_from_directory(INTERFACE_DIR, filename, max_age=GLB_MAX_AGE_SECONDS)
    return send_from_directory(INTERFACE_DIR, filename)


@app.get("/")
def dashboard():
    if session.get("user_id") is None:
        return redirect(url_for("login"))

    with closing(sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        assigned_id = session.get("astronaut_id")
        crew_rows = []
        if assigned_id is not None:
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(astronauts)")
            }
            assigned_crew = None
            if "crew" in columns:
                owner = conn.execute(
                    "SELECT crew FROM astronauts WHERE id = ?", (assigned_id,)
                ).fetchone()
                if owner is not None:
                    assigned_crew = owner["crew"]

            if assigned_crew is not None and assigned_crew.strip():
                crew_rows = conn.execute(
                    """SELECT id, first_name, last_name
                       FROM astronauts
                       WHERE crew = ?
                       ORDER BY id""",
                    (assigned_crew,),
                ).fetchall()
            else:
                crew_rows = conn.execute(
                    """SELECT id, first_name, last_name
                       FROM astronauts
                       WHERE id = ?
                       ORDER BY id""",
                    (assigned_id,),
                ).fetchall()

        requested_id = request.args.get("astronaut_id")
        if requested_id is not None:
            try:
                astronaut_id = int(requested_id)
            except ValueError:
                abort(400, description="astronaut_id must be an integer")
            if not any(row["id"] == astronaut_id for row in crew_rows):
                abort(404)
        else:
            if assigned_id is not None and any(row["id"] == assigned_id for row in crew_rows):
                return redirect(url_for("dashboard", astronaut_id=assigned_id))
            astronaut_id = None

        astronaut = None
        average_heart_rate = None
        extras = {}
        if astronaut_id is not None:
            astronaut = conn.execute(
                """SELECT a.id, a.first_name, a.last_name, a.age, a.height, a.weight,
                          m.recorded_at, m.average_pulse, m.systolic_pressure,
                          m.diastolic_pressure, m.bmi, m.glucose, m.sleep_hours,
                          m.stress_level, m.muscle_mass_percentage,
                          m.body_fat_percentage, m.radiation_levels, m.bone_density
                   FROM astronauts AS a
                   LEFT JOIN measurement_history AS m
                       ON m.id = (
                           SELECT latest.id
                           FROM measurement_history AS latest
                           WHERE latest.astronaut_id = a.id
                           ORDER BY latest.recorded_at DESC, latest.id DESC
                           LIMIT 1
                       )
                   WHERE a.id = ?""",
                (astronaut_id,),
            ).fetchone()
            average_pulse = conn.execute(
                "SELECT AVG(average_pulse) FROM measurement_history WHERE astronaut_id = ?",
                (astronaut_id,),
            ).fetchone()[0]
            for extra in HISTORY_EXTRAS:
                series = extra_series(conn, astronaut_id, extra)
                extras[extra.key] = series[-1][1] if series else None
            if average_pulse is not None:
                average_heart_rate = round(average_pulse, 1)

    crew = [
        {
            "id": row["id"],
            "full_name": f"{row['first_name']} {row['last_name']}".strip(),
        }
        for row in crew_rows
    ]
    latest = astronaut
    metrics = {
        "heart_rate": _format_measurement(latest["average_pulse"] if latest else None),
        "average_heart_rate": _format_measurement(average_heart_rate, "BPM"),
        "sleep": _format_measurement(latest["sleep_hours"] if latest else None),
        "bone_density": _format_measurement(
            latest["bone_density"] if latest else None, "g/cm²"
        ),
        "recovery": _format_measurement(extras.get("HEART_RATE_RECOVERY"), "bpm"),
        "vo2": _format_measurement(extras.get("VO2_MAX"), "mL/kg/min"),
    }

    return render_template(
        "Med-Point .html",
        astronaut=astronaut,
        crew=crew,
        metrics=metrics,
        is_authenticated=session.get("user_id") is not None,
    )


def _parse_phase(raw: str | None) -> MissionPhase | None:
    """Return the phase for a ?phase= value (missing means UNKNOWN); None when invalid."""
    if raw is None:
        return MissionPhase.UNKNOWN
    try:
        return MissionPhase(raw)
    except ValueError:
        return None

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") is not None:
        return redirect("/")
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        if len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return render_template("login.html", error="Enter a valid email address."), 400
        elif len(password) < 8 or len(password) > 128:
            return render_template(
                "login.html", error="Password must be between 8 and 128 characters."
            ), 400
        with closing(sqlite3.connect(DATABASE_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                _ensure_user_accounts_table(conn)
            user = conn.execute(
                "SELECT id, password_hash, astronaut_id FROM user_accounts WHERE email = ?",
                (email,),
            ).fetchone()
        if user is None:
            error = "Email or password is incorrect."
        elif not check_password_hash(user["password_hash"], password):
            error = "Email or password is incorrect."
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["astronaut_id"] = user["astronaut_id"]
            return redirect(
                url_for("dashboard", astronaut_id=user["astronaut_id"])
                if user["astronaut_id"] is not None
                else url_for("dashboard")
            )
    else:
        return render_template(
            "login.html", registered=request.args.get("registered") == "1", error=error
        )
    return render_template("login.html", error=error), 401


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    values = {}
    with closing(sqlite3.connect(DATABASE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        with conn:
            _ensure_astronaut_crew_column(conn)
        crew_options = _available_crew(conn)

    if request.method == "GET":
        return render_template("signup.html", values=values, crew_options=crew_options)

    full_name = " ".join(request.form.get("full_name", "").split())
    email = request.form.get("email", "").strip().casefold()
    password = request.form.get("password", "")
    crew_name = " ".join(request.form.get("crew", "").split())
    crew_names = {name.casefold(): name for name in crew_options}
    crew_name = crew_names.get(crew_name.casefold(), crew_name)
    values = {
        "full_name": full_name,
        "email": email,
        "age": request.form.get("age", ""),
        "height_cm": request.form.get("height_cm", ""),
        "weight_kg": request.form.get("weight_kg", ""),
        "crew": crew_name,
    }

    if not full_name or len(full_name) > 120:
        error = "Enter your full name (up to 120 characters)."
    elif len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        error = "Enter a valid email address."
    elif len(password) < 8 or len(password) > 128:
        error = "Password must be between 8 and 128 characters."
    elif not crew_name:
        error = "Choose an existing crew or enter a name for a new one."
    elif len(crew_name) > 80 or re.search(r"[\x00-\x1f\x7f]", crew_name):
        error = "Crew names must be at most 80 characters and contain no control characters."
    else:
        try:
            age = int(request.form.get("age", ""))
            height_cm = float(request.form.get("height_cm", ""))
            weight_kg = float(request.form.get("weight_kg", ""))
        except ValueError:
            error = "Enter a valid age, height, and weight."
        else:
            if not 0 <= age <= 120:
                error = "Age must be between 0 and 120 years."
            elif not math.isfinite(height_cm) or not 50 <= height_cm <= 300:
                error = "Height must be between 50 and 300 cm."
            elif not math.isfinite(weight_kg) or not 1 <= weight_kg <= 1000:
                error = "Weight must be between 1 and 1000 kg."
            else:
                duplicate_email = False
                duplicate_astronaut = False
                with closing(sqlite3.connect(DATABASE_PATH)) as conn:
                    conn.row_factory = sqlite3.Row
                    with conn:
                        _ensure_user_accounts_table(conn)
                        _ensure_astronaut_crew_column(conn)
                        duplicate_email = conn.execute(
                            "SELECT 1 FROM user_accounts WHERE email = ?", (email,)
                        ).fetchone() is not None
                        name_parts = full_name.split(maxsplit=1)
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) == 2 else ""
                        if not duplicate_email:
                            duplicate_astronaut = conn.execute(
                                """SELECT 1 FROM astronauts
                                   WHERE first_name = ? AND last_name = ?""",
                                (first_name, last_name),
                            ).fetchone() is not None
                        if not duplicate_email and not duplicate_astronaut:
                            account = conn.execute(
                                """INSERT INTO user_accounts
                                       (email, password_hash, full_name, age, height_cm, weight_kg)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (
                                    email,
                                    generate_password_hash(password),
                                    full_name,
                                    age,
                                    height_cm,
                                    weight_kg,
                                ),
                            )
                            astronaut = conn.execute(
                                """INSERT INTO astronauts
                                       (first_name, last_name, age, height, weight, crew)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (
                                    first_name,
                                    last_name,
                                    age,
                                    height_cm,
                                    weight_kg,
                                    crew_name,
                                ),
                            )
                            conn.execute(
                                "UPDATE user_accounts SET astronaut_id = ? WHERE id = ?",
                                (astronaut.lastrowid, account.lastrowid),
                            )
                if duplicate_email:
                    return (
                        render_template(
                            "signup.html",
                            values=values,
                            crew_options=crew_options,
                            error="An account with this email already exists.",
                        ),
                        409,
                    )
                if duplicate_astronaut:
                    return (
                        render_template(
                            "signup.html",
                            values=values,
                            crew_options=crew_options,
                            error="An astronaut with this name already exists.",
                        ),
                        409,
                    )
                return redirect(url_for("login", registered="1"))

    return render_template(
        "signup.html", values=values, crew_options=crew_options, error=error
    ), 400


@app.get("/api/astronauts/<int:astronaut_id>/recommendations")
def astronaut_recommendations(astronaut_id: int):
    phase = _parse_phase(request.args.get("phase"))
    if phase is None:
        allowed = ", ".join(member.value for member in MissionPhase)
        return jsonify(error=f"phase must be one of: {allowed}"), 400
    with closing(sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)) as conn:
        payload = payload_for_astronaut(conn, astronaut_id, phase)
    if payload is None:
        return jsonify(error="astronaut not found"), 404
    return jsonify(payload)


@app.get("/api/astronauts/<int:astronaut_id>/daily-tasks")
def astronaut_daily_tasks(astronaut_id: int):
    if session.get("user_id") is None:
        return jsonify(error="authentication required"), 401

    with closing(sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        if conn.execute(
            "SELECT 1 FROM astronauts WHERE id = ?", (astronaut_id,)
        ).fetchone() is None:
            return jsonify(error="astronaut not found"), 404

        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        history_columns = (
            {row["name"] for row in conn.execute("PRAGMA table_info(measurement_history)")}
            if "measurement_history" in tables
            else set()
        )
        task_expressions = []
        for key, _label, column in DAILY_TASK_CHARACTERISTICS:
            if column in history_columns and "recorded_at" in history_columns:
                task_expressions.append(
                    f"""MAX(CASE WHEN date(recorded_at, 'localtime')
                                            = date('now', 'localtime')
                                   AND {column} IS NOT NULL
                                THEN 1 ELSE 0 END) AS "{key}" """
                )
            else:
                task_expressions.append(f'0 AS "{key}"')

        if "measurement_history" in tables:
            row = conn.execute(
                f"""SELECT {", ".join(task_expressions)}
                    FROM measurement_history
                    WHERE astronaut_id = ?""",
                (astronaut_id,),
            ).fetchone()
            tasks = [
                {"key": key, "label": label, "checked": bool(row[key])}
                for (key, label, _column) in DAILY_TASK_CHARACTERISTICS
            ]
        else:
            tasks = [
                {"key": key, "label": label, "checked": False}
                for key, label, _column in DAILY_TASK_CHARACTERISTICS
            ]
        today = conn.execute("SELECT date('now', 'localtime')").fetchone()[0]

    return jsonify(astronaut_id=astronaut_id, today=today, tasks=tasks)


if __name__ == "__main__":
    app.run()
