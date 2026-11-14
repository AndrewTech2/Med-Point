# Required calculations based on characteristics

Written for: developers on this project who will implement the calculations.

Input names match the enum members in [Caracteristici.py](Caracteristici.py). Units are listed there too.

| Key | Characteristic | Unit |
|---|---|---|
| `VARSTA` | Age | years |
| `MASA_CORPORALA` | Body weight | kg |
| `INALTIME` | Height | cm |
| `INDICE_MASA_CORPORALA` | Body mass index | kg/m² |
| `PULS_MEDIU` | Average heart rate | bpm |
| `PRESIUNE_SISTOLICA` | Systolic blood pressure | mmHg |
| `PRESIUNE_DIASTOLICA` | Diastolic blood pressure | mmHg |
| `PROCENT_MASA_MUSCULARA` | Muscle mass percentage | % |
| `PROCENT_GRASIME` | Body fat percentage | % |
| `NIVEL_STRES` | Stress level | scale |
| `NIVELE_RADIATIE` | Mission radiation exposure limit | mSv |
| `DENSITATE_OSOASA_CALCIU` | Bone density (calcium) | g/cm² |
| `GLICEMIE` | Blood glucose | mg/dL |
| `ORE_SOMN` | Sleep duration | hours |

## Calculations

### 1. Body mass index (BMI)

- **Inputs:** `MASA_CORPORALA`, `INALTIME`
- **Formula:** `BMI = mass_kg / (height_m ** 2)`, where `height_m = INALTIME / 100`
- **Output:** `INDICE_MASA_CORPORALA`, rounded to one decimal
- **Note:** `INDICE_MASA_CORPORALA` also appears in the input list. Decide whether it is measured or always derived. If it is always derived, remove it from the input list.

### 2. Fat mass

- **Inputs:** `MASA_CORPORALA`, `PROCENT_GRASIME`
- **Formula:** `fat_mass_kg = MASA_CORPORALA * PROCENT_GRASIME / 100`

### 3. Lean mass (without fat)

- **Inputs:** `MASA_CORPORALA`, `PROCENT_GRASIME`
- **Formula:** `lean_mass_kg = MASA_CORPORALA - fat_mass_kg`

### 4. Muscle mass in kg

- **Inputs:** `MASA_CORPORALA`, `PROCENT_MASA_MUSCULARA`
- **Formula:** `muscle_mass_kg = MASA_CORPORALA * PROCENT_MASA_MUSCULARA / 100`

### 5. BMI category

- **Inputs:** `INDICE_MASA_CORPORALA` (or the result of calculation 1)
- **Thresholds (WHO):** under 18.5 underweight; 18.5 to under 25 normal; 25 to under 30 overweight; 30 and above obese
- **Output:** category label

### 6. Blood pressure category

- **Inputs:** `PRESIUNE_SISTOLICA`, `PRESIUNE_DIASTOLICA`
- **Thresholds (adult, typical):** normal below 120 and below 80; elevated 120 to 129 and below 80; high from 130 or 80 upward; low below 90 or below 60. The higher category of the two values applies.
- **Note:** thresholds must be confirmed for a space mission. Input already checks that systolic is greater than diastolic.

### 7. Heart rate category

- **Inputs:** `PULS_MEDIU`
- **Thresholds (resting adult):** under 60 bradycardia; 60 to 100 normal; above 100 tachycardia
- **Note:** the thresholds apply to resting pulse. Confirm with the astronaut-health specification whether a different range is needed in flight.

### 8. Blood glucose category

- **Inputs:** `GLICEMIE` (mg/dL)
- **Thresholds (fasting, typical adult):** under 70 low; 70 to 99 normal; 100 to 125 prediabetes range; 126 and above high
- **Note:** thresholds depend on whether the reading is fasting. Add a fasting flag if needed.

### 9. Sleep deficit

- **Inputs:** `ORE_SOMN`, `VARSTA`
- **Formula:** `sleep_deficit = recommended(VARSTA) - ORE_SOMN`, where `recommended` is the recommended sleep for the age group (adults usually 7 to 9 hours; confirm the exact value)
- **Output:** hours of deficit (negative means surplus)

### 10. Stress level

- **Inputs:** `NIVEL_STRES`
- **Note:** the README does not say what scale is used. Once the scale is known (e.g. 1 to 10), add thresholds for low, medium, and high.

### 11. Mission radiation exposure limit

- **Inputs:** `NIVELE_RADIATIE`
- **Typical mission-use bounds:** under 50 mSv is low; 50 to 100 mSv is moderate; above 100 mSv is high, but the final thresholds should be confirmed against the mission profile and agency limits.
- **Output:** mission radiation exposure class

### 12. Bone density (calcium)

- **Inputs:** `DENSITATE_OSOASA_CALCIU`
- **Typical adult bone mineral density:** around 0.9 to 1.4 g/cm² is healthy; lower values indicate bone loss and higher values are unusual for a healthy adult.
- **Output:** bone density category (normal/warning/critical)

### 13. Estimated maximum heart rate (optional)

- **Inputs:** `VARSTA`, `PULS_MEDIU`
- **Formula:** `fc_max = 220 - VARSTA`
- **Use:** percentage of maximum heart rate during activity, if exercise monitoring is needed

## Open decisions

1. Is `INDICE_MASA_CORPORALA` measured or derived?
2. ~~How is blood pressure stored?~~ Decided: two values, systolic and diastolic.
3. What scale is `NIVEL_STRES` on?
4. Which thresholds are authoritative for a space mission? The values above are general adult references and must be confirmed.
5. The README has a typo in the pulse line: `<li>Average heart rate<li>` is missing `</li>`. Fix it if the README is used as a source.
