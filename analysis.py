import sqlite3
import pandas as pd


# Names used by the existing database schema (the schema itself uses Romanian identifiers).
DB_FILE = "astronauti.db"
TABLE_NAME = "astronauti"
LAST_NAME_COLUMN = "nume"
FIRST_NAME_COLUMN = "prenume"
PULSE_COLUMN = "puls_mediu"
SYSTOLIC_COLUMN = "presiune_sistolica"
BMI_COLUMN = "indice_masa_corporala"
RADIATION_COLUMN = "nivele_radiatie"
BONE_DENSITY_COLUMN = "densitate_osoasa_calciu"


conn = sqlite3.connect(DB_FILE)


try:
    conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {RADIATION_COLUMN} REAL")
    conn.commit()
except:
    pass

try:
    conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {BONE_DENSITY_COLUMN} REAL")
    conn.commit()
except:
    pass

df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
conn.close()

print("=== ASTRONAUT MEDICAL ANALYSIS REPORT ===")

if df.empty:
    print("No astronauts found in database.")
else:
    for index, row in df.iterrows():
        full_name = row[LAST_NAME_COLUMN] + " " + row[FIRST_NAME_COLUMN]
        print(f"\nAstronaut: {full_name}")



        # 1. Pulse check
        pulse = row[PULSE_COLUMN]
        if pd.isna(pulse):
            pulse_status = "Unknown"
        elif pulse < 50 or pulse > 115:
            pulse_status = "Critical"
        elif (50 <= pulse < 60) or (100 < pulse <= 115):
            pulse_status = "Warning"
        else:
            pulse_status = "Healthy"

        print(f"  - Pulse: {pulse_status}")

        # 2. Systolic check
        sys_val = row[SYSTOLIC_COLUMN]
        if pd.isna(sys_val):
            sys_status = "Unknown"
        elif sys_val < 90 or sys_val >= 140:
            sys_status = "Critical"
        elif sys_val > 120 and sys_val <= 139:
            sys_status = "Warning"
        else:
            sys_status = "Healthy"

        print(f"  - Systolic Pressure: {sys_status}")

        # 3. BMI check
        bmi_val = row[BMI_COLUMN]
        if pd.isna(bmi_val):
            bmi_status = "Unknown"
        elif bmi_val < 17.0 or bmi_val >= 30.0:
            bmi_status = "Critical"
        elif (17.0 <= bmi_val < 18.5) or (25.0 < bmi_val <= 29.9):
            bmi_status = "Warning"
        else:
            bmi_status = "Healthy"

        print(f"  - BMI: {bmi_status}")


        statuses = [pulse_status, sys_status, bmi_status]

        if RADIATION_COLUMN in row and not pd.isna(row[RADIATION_COLUMN]):
            rad = row[RADIATION_COLUMN]
            if rad > 100:
                rad_status = "Critical"
            elif rad > 50 and rad <= 100:
                rad_status = "Warning"
            else:
                rad_status = "Healthy"
            print(f"  - Radiation: {rad_status}")
            statuses.append(rad_status)

        if BONE_DENSITY_COLUMN in row and not pd.isna(row[BONE_DENSITY_COLUMN]):
            bone = row[BONE_DENSITY_COLUMN]
            if bone < 0.7 or bone > 1.6:
                bone_status = "Critical"
            elif (0.7 <= bone < 0.9) or (1.4 < bone <= 1.6):
                bone_status = "Warning"
            else:
                bone_status = "Healthy"
            print(f"  - Bone Density: {bone_status}")
            statuses.append(bone_status)


        active_statuses = []
        for s in statuses:
            if s != "Unknown":
                active_statuses.append(s)

        if "Critical" in active_statuses:
            global_status = "Critical"
        elif "Warning" in active_statuses:
            global_status = "Warning"
        else:
            global_status = "Healthy"

        print(f"  --> Overall Status: [{global_status}]")
        print("-" * 40)
