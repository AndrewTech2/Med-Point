CREATE TABLE IF NOT EXISTS astronauts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER, 
    height REAL,
    weight REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS measurement_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    astronaut_id INTEGER NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    average_pulse REAL,
    systolic_pressure REAL,
    diastolic_pressure REAL,
    bmi REAL,
    glucose REAL,
    sleep_hours REAL,
    stress_level REAL,
    muscle_mass_percentage REAL,
    body_fat_percentage REAL,
    radiation_levels REAL,
    bone_density REAL,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts (id) ON DELETE CASCADE
);