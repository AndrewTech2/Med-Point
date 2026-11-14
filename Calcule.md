# Calcule necesare pe baza caracteristicilor

Written for: developers on this project who will implement the calculations.

Input names match the enum members in [Caracteristici.py](Caracteristici.py). Units are listed there too.

| Key | Caracteristica | Unitate |
|---|---|---|
| `VARSTA` | Vârstă | ani |
| `MASA_CORPORALA` | Masă corporală | kg |
| `INALTIME` | Înălțime | cm |
| `INDICE_MASA_CORPORALA` | Indicele de masă corporală | kg/m² |
| `PULS_MEDIU` | Pulsul mediu | bpm |
| `PRESIUNE_SISTOLICA` | Presiunea arterială sistolică | mmHg |
| `PRESIUNE_DIASTOLICA` | Presiunea arterială diastolică | mmHg |
| `PROCENT_MASA_MUSCULARA` | Procent de masă musculară | % |
| `PROCENT_GRASIME` | Procent de grăsime | % |
| `NIVEL_STRES` | Niveluri de stres | scală |
| `GLICEMIE` | Glicemia din sânge | mg/dL |
| `ORE_SOMN` | Orele petrecute dormind | ore |

## Calculations

### 1. Indicele de masă corporală (BMI)

- **Inputs:** `MASA_CORPORALA`, `INALTIME`
- **Formula:** `BMI = masa_kg / (inaltime_m ** 2)`, where `inaltime_m = INALTIME / 100`
- **Output:** `INDICE_MASA_CORPORALA`, rounded to one decimal
- **Note:** `INDICE_MASA_CORPORALA` is also in the input list. Decide whether it is measured or always derived. If it is always derived, drop it as an input.

### 2. Masa de grăsime

- **Inputs:** `MASA_CORPORALA`, `PROCENT_GRASIME`
- **Formula:** `masa_grasime_kg = MASA_CORPORALA * PROCENT_GRASIME / 100`

### 3. Masa slabă (fără grăsime)

- **Inputs:** `MASA_CORPORALA`, `PROCENT_GRASIME`
- **Formula:** `masa_slaba_kg = MASA_CORPORALA - masa_grasime_kg`

### 4. Masa musculară în kg

- **Inputs:** `MASA_CORPORALA`, `PROCENT_MASA_MUSCULARA`
- **Formula:** `masa_musculara_kg = MASA_CORPORALA * PROCENT_MASA_MUSCULARA / 100`

### 5. Categoria BMI

- **Inputs:** `INDICE_MASA_CORPORALA` (or the result of calculation 1)
- **Thresholds (WHO):** under 18.5 underweight; 18.5 to under 25 normal; 25 to under 30 overweight; 30 and above obese
- **Output:** category label

### 6. Categoria tensiunii arteriale

- **Inputs:** `PRESIUNE_SISTOLICA`, `PRESIUNE_DIASTOLICA`
- **Thresholds (adult, typical):** normal below 120 and below 80; elevated 120 to 129 and below 80; high from 130 or 80 upward; low below 90 or below 60. The higher category of the two values applies.
- **Note:** thresholds must be confirmed for a space mission. Input already checks that systolic is greater than diastolic.

### 7. Categoria pulsului

- **Inputs:** `PULS_MEDIU`
- **Thresholds (resting adult):** under 60 bradycardia; 60 to 100 normal; above 100 tachycardia
- **Note:** the thresholds apply to resting pulse. Confirm with the astronaut-health spec whether a different range is needed in flight.

### 8. Categoria glicemiei

- **Inputs:** `GLICEMIE` (mg/dL)
- **Thresholds (fasting, typical adult):** under 70 low; 70 to 99 normal; 100 to 125 prediabetes range; 126 and above high
- **Note:** thresholds depend on whether the reading is fasting. Add a fasting flag if needed.

### 9. Deficitul de somn

- **Inputs:** `ORE_SOMN`, `VARSTA`
- **Formula:** `deficit_somn = recomandat(VARSTA) - ORE_SOMN`, where `recomandat` is the recommended sleep for the age group (adults usually 7 to 9 hours; confirm the exact value)
- **Output:** hours of deficit (negative means surplus)

### 10. Nivelul de stres

- **Inputs:** `NIVEL_STRES`
- **Note:** the README does not say what scale is used. Once the scale is known (e.g. 1 to 10), add thresholds for low, medium, and high.

### 11. Frecvența cardiacă maximă estimată (optional)

- **Inputs:** `VARSTA`, `PULS_MEDIU`
- **Formula:** `fc_max = 220 - VARSTA`
- **Use:** percentage of max heart rate during activity, if exercise monitoring is needed

## Open decisions

1. Is `INDICE_MASA_CORPORALA` measured or derived?
2. ~~How is blood pressure stored?~~ Decided: two values, systolic and diastolic.
3. Which scale is `NIVEL_STRES` on?
4. Which thresholds are authoritative for a space mission? The values above are general adult references and must be confirmed.
5. The README has a typo in the pulse line: `<li>Pulsul mediu<li>` is missing `</li>`. Fix it if the README is used as a source.
