import sqlite3
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
INTERFACE_DIR = BASE_DIR / "Med-Point-fixed" / "Med-Point Interface"
DATABASE_PATH = BASE_DIR / "astronauts.db"

app = Flask(
    __name__,
    template_folder=str(INTERFACE_DIR),
    static_folder=None,
)

ASSET_EXTENSIONS = {".css", ".glb", ".js"}


def _format_measurement(value: float | int | None, unit: str = "") -> str:
    if value is None:
        return "—"
    formatted = f"{value:g}"
    return f"{formatted} {unit}".strip()


@app.get("/<path:filename>")
def interface_asset(filename: str):
    if Path(filename).suffix.lower() not in ASSET_EXTENSIONS:
        abort(404)
    return send_from_directory(INTERFACE_DIR, filename)


@app.get("/")
def dashboard():
    with sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        crew_rows = conn.execute(
            """SELECT id, first_name, last_name
               FROM astronauts
               ORDER BY id"""
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
            astronaut_id = crew_rows[0]["id"] if crew_rows else None

        astronaut = None
        history = []
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
            history = conn.execute(
                """SELECT recorded_at, average_pulse, sleep_hours
                   FROM measurement_history
                   WHERE astronaut_id = ?
                   ORDER BY recorded_at, id""",
                (astronaut_id,),
            ).fetchall()

    crew = [
        {
            "id": row["id"],
            "full_name": f"{row['first_name']} {row['last_name']}",
        }
        for row in crew_rows
    ]
    latest = astronaut
    heart_rate_values = [row["average_pulse"] for row in history if row["average_pulse"] is not None]
    average_heart_rate = (
        sum(heart_rate_values) / len(heart_rate_values) if heart_rate_values else None
    )
    metrics = {
        "heart_rate": _format_measurement(latest["average_pulse"] if latest else None),
        "average_heart_rate": _format_measurement(average_heart_rate, "BPM"),
        "sleep": _format_measurement(latest["sleep_hours"] if latest else None),
        "bone_density": _format_measurement(
            latest["bone_density"] if latest else None, "g/cm²"
        ),
        "recovery": "—",
        "vo2": "—",
    }

    return render_template(
        "Med-Point.html",
        astronaut=astronaut,
        crew=crew,
        metrics=metrics,
    )


if __name__ == "__main__":
    app.run()
