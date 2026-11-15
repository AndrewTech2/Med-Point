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

Start the application:

```bash
python3 app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. The repository includes an `astronauts.db` SQLite database with sample astronaut and measurement-history records. The app reads and updates this database; keep a backup before making changes.

The dashboard loads its web fonts and 3D model-viewer library from external CDNs, so internet access is needed for those assets.

## Medical-use notice

Med-Point is a tracking and demonstration application, not a medical device or a substitute for clinical judgment. Recommendation thresholds and guidance are informational and must be reviewed by the mission medical team before operational use. The project’s calculations and proposed thresholds may be incomplete or unverified.
