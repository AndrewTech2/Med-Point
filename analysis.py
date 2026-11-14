import sqlite3
import pandas as pd

# Conectare simpla, fara Pathlib complicat
conn = sqlite3.connect("astronauti.db")

# Hack clasic de incepator pentru migrare: incercam sa adaugam coloanele si ignoram eroarea daca exista deja
try:
    conn.execute("ALTER TABLE astronauti ADD COLUMN nivele_radiatie REAL")
    conn.commit()
except:
    pass

try:
    conn.execute("ALTER TABLE astronauti ADD COLUMN densitate_osoasa_calciu REAL")
    conn.commit()
except:
    pass

df = pd.read_sql_query("SELECT * FROM astronauti", conn)
conn.close()

print("=== ASTRONAUT MEDICAL ANALYSIS REPORT ===")

if df.empty:
    print("No astronauts found in database.")
else:
    for index, row in df.iterrows():
        # Concatenare simpla de string-uri
        full_name = row['nume'] + " " + row['prenume']
        print(f"\nAstronaut: {full_name}")
        
        # O multime de blocuri repetitive copiate si lipite (specific pentru codul de incepator)
        
        # 1. Pulse check
        puls = row['puls_mediu']
        if pd.isna(puls):
            pulse_status = "Unknown"
        elif puls < 50 or puls > 115:
            pulse_status = "Critical"
        elif (50 <= puls < 60) or (100 < puls <= 115):
            pulse_status = "Warning"
        else:
            pulse_status = "Healthy"
            
        print(f"  - Pulse: {pulse_status}")

        # 2. Systolic check
        sys_val = row['presiune_sistolica']
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
        bmi_val = row['indice_masa_corporala']
        if pd.isna(bmi_val):
            bmi_status = "Unknown"
        elif bmi_val < 17.0 or bmi_val >= 30.0:
            bmi_status = "Critical"
        elif (17.0 <= bmi_val < 18.5) or (25.0 < bmi_val <= 29.9):
            bmi_status = "Warning"
        else:
            bmi_status = "Healthy"
            
        print(f"  - BMI: {bmi_status}")

        # Tinem minte statusurile intr-o lista simpla
        statuses = [pulse_status, sys_status, bmi_status]
        
        # Verificam coloanele optionale manual, direct in bucla
        if 'nivele_radiatie' in row and not pd.isna(row['nivele_radiatie']):
            rad = row['nivele_radiatie']
            if rad > 100:
                rad_status = "Critical"
            elif rad > 50 and rad <= 100:
                rad_status = "Warning"
            else:
                rad_status = "Healthy"
            print(f"  - Radiation: {rad_status}")
            statuses.append(rad_status)

        if 'densitate_osoasa_calciu' in row and not pd.isna(row['densitate_osoasa_calciu']):
            bone = row['densitate_osoasa_calciu']
            if bone < 0.7 or bone > 1.6:
                bone_status = "Critical"
            elif (0.7 <= bone < 0.9) or (1.4 < bone <= 1.6):
                bone_status = "Warning"
            else:
                bone_status = "Healthy"
            print(f"  - Bone Density: {bone_status}")
            statuses.append(bone_status)

        # Calcularea statusului global cu un for clasic in loc de list comprehension avansat
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