CREATE TABLE IF NOT EXISTS astronauts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER, 
    height REAL,
    weight REAL,
    crew VARCHAR(255    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
    height_cm REAL NOT NULL CHECK (height_cm BETWEEN 50 AND 300),
    weight_kg REAL NOT NULL CHECK (weight_kg BETWEEN 1 AND 1000),
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