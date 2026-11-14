# Required calculations based on characteristics

Written for: developers on this project who will implement the calculations.

Input names match the enum members in [Caracteristici.py](Caracteristici.py). The database stores astronaut details in `astronauts` and measurements in `measurement_history`.

| Key | Characteristic | Unit |
|---|---|---|
| `AGE` | Age | years |
| `BODY_WEIGHT` | Body weight | kg |
| `HEIGHT` | Height | cm |
| `BODY_MASS_INDEX` | Body mass index | kg/m² |
| `AVERAGE_HEART_RATE` | Average heart rate | bpm |
| `SYSTOLIC_BLOOD_PRESSURE` | Systolic blood pressure | mmHg |
| `DIASTOLIC_BLOOD_PRESSURE` | Diastolic blood pressure | mmHg |
| `MUSCLE_MASS_PERCENTAGE` | Muscle mass percentage | % |
| `BODY_FAT_PERCENTAGE` | Body fat percentage | % |
| `STRESS_LEVEL` | Stress level | scale |
| `MISSION_RADIATION_LEVEL` | Mission radiation exposure level | mSv |
| `BONE_DENSITY_CALCIUM` | Bone density (calcium) | g/cm² |
| `BLOOD_GLUCOSE` | Blood glucose | mg/dL |
| `SLEEP_HOURS` | Sleep duration | hours |

## Calculations

### 1. Body mass index (BMI)

- **Inputs:** `BODY_WEIGHT`, `HEIGHT`
- **Formula:** `BMI = mass_kg / (height_m ** 2)`, where `height_m = HEIGHT / 100`
- **Output:** `BODY_MASS_INDEX`, rounded to one decimal
- **Note:** `BODY_MASS_INDEX` also appears in the input list. Decide whether it is measured or always derived. If it is always derived, remove it from the input list.

### 2. Fat mass

- **Inputs:** `BODY_WEIGHT`, `BODY_FAT_PERCENTAGE`
- **Formula:** `fat_mass_kg = BODY_WEIGHT * BODY_FAT_PERCENTAGE / 100`

### 3. Lean mass (without fat)

- **Inputs:** `BODY_WEIGHT`, `BODY_FAT_PERCENTAGE`
- **Formula:** `lean_mass_kg = BODY_WEIGHT - fat_mass_kg`

### 4. Muscle mass in kg

- **Inputs:** `BODY_WEIGHT`, `MUSCLE_MASS_PERCENTAGE`
- **Formula:** `muscle_mass_kg = BODY_WEIGHT * MUSCLE_MASS_PERCENTAGE / 100`

### 5. BMI category

- **Inputs:** `BODY_MASS_INDEX` (or the result of calculation 1)
- **Thresholds (WHO):** under 18.5 underweight; 18.5 to under 25 normal; 25 to under 30 overweight; 30 and above obese
- **Output:** category label

### 6. Blood pressure category

- **Inputs:** `SYSTOLIC_BLOOD_PRESSURE`, `DIASTOLIC_BLOOD_PRESSURE`
- **Thresholds (adult, typical):** normal below 120 and below 80; elevated 120 to 129 and below 80; high from 130 or 80 upward; low below 90 or below 60. The higher category of the two values applies.
- **Note:** thresholds must be confirmed for a space mission. Input already checks that systolic is greater than diastolic.

### 7. Heart rate category

- **Inputs:** `AVERAGE_HEART_RATE`
- **Thresholds (resting adult):** under 60 bradycardia; 60 to 100 normal; above 100 tachycardia
- **Note:** the thresholds apply to resting pulse. Confirm with the astronaut-health specification whether a different range is needed in flight.

### 8. Blood glucose category

- **Inputs:** `BLOOD_GLUCOSE` (mg/dL)
- **Thresholds (fasting, typical adult):** under 70 low; 70 to 99 normal; 100 to 125 prediabetes range; 126 and above high
- **Note:** thresholds depend on whether the reading is fasting. Add a fasting flag if needed.

### 9. Sleep deficit

- **Inputs:** `SLEEP_HOURS`, `AGE`
- **Formula:** `sleep_deficit = recommended(AGE) - SLEEP_HOURS`, where `recommended` is the recommended sleep for the age group (adults usually 7 to 9 hours; confirm the exact value)
- **Output:** hours of deficit (negative means surplus)

### 10. Stress level

- **Inputs:** `STRESS_LEVEL`
- **Note:** the README does not say what scale is used. Once the scale is known (e.g. 1 to 10), add thresholds for low, medium, and high.

### 11. Mission radiation exposure limit

- **Inputs:** `MISSION_RADIATION_LEVEL`
- **Typical mission-use bounds:** under 50 mSv is low; 50 to 100 mSv is moderate; above 100 mSv is high, but the final thresholds should be confirmed against the mission profile and agency limits.
- **Output:** mission radiation exposure class

### 12. Bone density (calcium)

- **Inputs:** `BONE_DENSITY_CALCIUM`
- **Typical adult bone mineral density:** around 0.9 to 1.4 g/cm² is healthy; lower values indicate bone loss and higher values are unusual for a healthy adult.
- **Output:** bone density category (normal/warning/critical)

### 13. Estimated maximum heart rate (optional)

- **Inputs:** `AGE`, `AVERAGE_HEART_RATE`
- **Formula:** `fc_max = 220 - AGE`
- **Use:** percentage of maximum heart rate during activity, if exercise monitoring is needed

## Extended calculations

Calculations 14-35 (mean arterial pressure, VO2max, FFMI, basal metabolic rate, bone loss rate, sleep debt, HRV, PSS-10, PVT lapses, cumulative radiation dose, hypertensive crisis and others), the candidate variables, the influence map and the recommendation system are in [calculations_extended.md](calculations_extended.md). They are implemented in [calculations.py](calculations.py) and tested in [test_calculations.py](test_calculations.py).

The `Characteristic` enum members map to columns in `astronauts` and `measurement_history` as follows:

| `Characteristic` member | Database column |
|---|---|
| `AGE` | `astronauts.age` |
| `BODY_WEIGHT` | `astronauts.weight` |
| `HEIGHT` | `astronauts.height` |
| `BODY_MASS_INDEX` | `measurement_history.bmi` |
| `AVERAGE_HEART_RATE` | `measurement_history.average_pulse` |
| `SYSTOLIC_BLOOD_PRESSURE` | `measurement_history.systolic_pressure` |
| `DIASTOLIC_BLOOD_PRESSURE` | `measurement_history.diastolic_pressure` |
| `MUSCLE_MASS_PERCENTAGE` | `measurement_history.muscle_mass_percentage` |
| `BODY_FAT_PERCENTAGE` | `measurement_history.body_fat_percentage` |
| `STRESS_LEVEL` | `measurement_history.stress_level` |
| `MISSION_RADIATION_LEVEL` | `measurement_history.radiation_levels` |
| `BONE_DENSITY_CALCIUM` | `measurement_history.bone_density` |
| `BLOOD_GLUCOSE` | `measurement_history.glucose` |
| `SLEEP_HOURS` | `measurement_history.sleep_hours` |

## Open decisions

1. Is `BODY_MASS_INDEX` measured or derived?
2. ~~How is blood pressure stored?~~ Decided: two values, systolic and diastolic.
3. What scale is `STRESS_LEVEL` on?
4. Which thresholds are authoritative for a space mission? The values above are general adult references and must be confirmed.
5. The README has a typo in the pulse line: `<li>Average heart rate<li>` is missing `</li>`. Fix it if the README is used as a source.
