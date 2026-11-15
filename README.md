# Med-Point

Med-Point is a web application for monitoring astronaut health during space missions. Its dashboard brings crew health measurements, historical trends, and informational recommendations together in one place, helping users follow changes that can be difficult to monitor when a crew is far from Earth.

## Features

- **Crew dashboard:** Review astronauts in a crew and switch between their health profiles.
- **Health metrics:** Track body mass index (BMI), average heart rate, systolic and diastolic blood pressure, muscle mass, body fat, stress, mission radiation exposure, bone density (calcium), blood glucose, and sleep duration.
- **Health history:** View measurement history and trends when data is available.
- **Recommendations:** See informational health recommendations based on recorded measurements, with support for mission-phase context.
- **Daily tracking checklist:** See which health measurements have been recorded for the selected astronaut today. Checklist status is based on the measurement history; it is not a form for entering measurements.
- **Visual dashboard:** Explore health information alongside an interactive astronaut model and crew overview.
- **Accounts:** Create an account, join or form a crew, sign in, and sign out.

## Technology

- **HTML** for dashboard, sign-in, and registration pages
- **CSS** for the responsive interface and dashboard components
- **JavaScript** for charts, crew and astronaut navigation, metric filters, recommendations, and the 3D model
- **Python / Flask** for the web application, account flows, and JSON endpoints
- **SQLite / SQL** for astronaut profiles, accounts, and measurement history

## Getting started

### Requirements

- Python 3.10 or later
- pip

### Install and run

From the repository root, install the Flask dependencies:

```bash
python3 -m pip install Flask Flask-Session
```

Set a persistent secret key for Flask sessions. For example, generate one with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
export MED_POINT_SECRET_KEY="<paste-generated-value-here>"
```

Replace the placeholder with the generated value. If `MED_POINT_SECRET_KEY` is not set, the app generates a new key at startup, so sessions will not persist across restarts.

Start the application:

```bash
python3 app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. The repository includes an `astronauts.db` SQLite database with sample astronaut and measurement-history records. The app reads and updates this database; keep a backup before making changes.

The dashboard loads its web fonts and 3D model-viewer library from external CDNs, so internet access is needed for those assets.

## Tests

Install pytest if needed, then run the test suite from the repository root:

```bash
python3 -m pip install pytest
python3 -m pytest
```

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Flask application, account routes, dashboard, and API endpoints |
| `Med-Point-fixed/Med-Point Interface/` | Active dashboard templates, stylesheets, and JavaScript |
| `Caracteristici.py` | Health characteristic definitions and database mappings |
| `calculations.py`, `recommendations.py`, `recommendation_rules.py` | Health calculations and recommendation logic |
| `recommendations_api.py` | Recommendation payloads served by the application |
| `astronauts.db` | SQLite database containing astronaut profiles and measurement history |
| `test_*.py` | Automated tests |
| `Calcule.md`, `calculations_extended.md` | Calculation notes, references, and proposed additional metrics |

## Medical-use notice

Med-Point is a tracking and demonstration application, not a medical device or a substitute for clinical judgment. Recommendation thresholds and guidance are informational and must be reviewed by the mission medical team before operational use. The project’s calculations and proposed thresholds may be incomplete or unverified.
