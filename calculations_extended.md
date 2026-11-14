# Extended calculations, candidate variables and recommendations

Written for: developers on this project who will implement the extra calculations.

This file only holds the **extra** parts. Calculations 1-13 and the characteristic table are in [Calcule.md](Calcule.md). Input names match the `Characteristic` enum in [Caracteristici.py](Caracteristici.py). The Python functions for calculations 14-35 are in [calculations.py](calculations.py).

> **Disclaimer.** All thresholds, status levels and recommendations in this document are informational. They come from general clinical references and spaceflight research (see [Sources](#sources)) and are not mission medical criteria. The mission flight surgeon / medical team must confirm every threshold and every action before use. Nothing here replaces a medical assessment.
>
> Source tags like `[S12]` point to the [Sources](#sources) list. `[unverified]` means a researcher reported the value but could not confirm it in a primary source. `[unsourced]` means no researcher found a source and the item is a proposal only. `[design]` means a software design choice made for this project, not a medical fact.

## Candidate variables (proposed, not yet in Caracteristici.py)

These are candidates to add later. "M" = measured (needs a new input), "D" = derived from other values (formula in the calculation section named in the last column). Proposed keys follow the existing naming style. None of these are in the database yet.

**A field that several formulas need:** `SEX` (M/F). Mifflin-St Jeor BMR, body fat bands, FFMI ranges, grip strength cut-points and the bone T-score reference all depend on sex [S19, S22, S23, S24]. Without it, those calculations cannot pick a range.

### Cardiovascular and blood

| Proposed key | Name | Unit | M/D | Typical range / reference | Why it matters for astronauts | Calc |
|---|---|---|---|---|---|---|
| `RESTING_PULSE` | Resting heart rate | bpm | M | 60-100 adult [unverified] | Separate from `AVERAGE_HEART_RATE` (average in flight). Rises at standing after landing in orthostatic intolerance [S1, S6] | 7 |
| `MEAN_ARTERIAL_PRESSURE` | Mean arterial pressure (MAP) | mmHg | D | about 70-100 [unverified] | Summary of perfusion pressure; useful for fluid-shift tracking | 14 |
| `PULSE_PRESSURE` | Pulse pressure | mmHg | D | about 40-60 [unverified] | Falls when stroke volume falls; reduced stroke volume is the main contributor to post-flight orthostatic intolerance [S4] | 15 |
| `MAX_HEART_RATE` | Max heart rate (Tanaka) | bpm | D | 208 - 0.7 x age [S18, unverified] | Exercise dosing; NASA aerobic guidance is given as % of peak HR [S8] | 16 |
| `HEART_RATE_RECOVERY` | Heart rate recovery at 1 min | bpm | D | drop of 12 or less is abnormal [unverified] | Fitness / autonomic marker | 17 |
| `VO2_MAX` | Aerobic capacity (VO2max / VO2peak) | mL/kg/min | M (exercise test) | no single range; use age/sex tables. Keep at or above 80% of preflight (NASA-STD-3001, snippet only) | Falls in most long-duration crew, +5% to -30% [S7, S10] | 18 |
| `ORTHOSTATIC_TEST` | Orthostatic test: change in SBP and HR, supine to standing 10 min | mmHg, bpm | M | cutoffs vary; not verified | Post-landing orthostatic intolerance in about 30% of astronauts (meta-analysis, 221 astronauts) [S4] | 19 |
| `HEMOGLOBIN` | Hemoglobin | g/dL | M (lab) | lab reference range [unverified] | Space anemia: red cell mass falls on missions over about 9 days [S11, S12] | rules |
| `HEMATOCRIT` | Hematocrit | % | M (lab) | lab reference range [unverified] | Same as above | rules |
| `HBA1C` | Glycated hemoglobin | % | M (lab) | prediabetes 5.7-6.4, diabetes 6.5 or more (ADA) [unverified] | Long-term glucose control; complements a single `BLOOD_GLUCOSE` reading | rules |
| `LDL_CHOLESTEROL` | LDL cholesterol | mg/dL | M (lab) | not found in sources [unsourced] | General cardiovascular risk | - |
| `PLASMA_VOLUME` | Plasma volume | mL | M (research only) | - | Fluid shift causes reflex hypovolemia [S1]. Tracer method, research setting only | - |

### Musculoskeletal and body composition

| Proposed key | Name | Unit | M/D | Typical range / reference | Why it matters for astronauts | Calc |
|---|---|---|---|---|---|---|
| `FFMI` | Fat-free mass index | kg/m² | D | normal-BMI adults: men 16.7-19.8, women 14.6-16.8 (Kyle 2003, via secondary) [S21] | Lean mass scaled to height; tracks muscle loss | 20 |
| `BONE_MINERAL_DENSITY` | Bone mineral density (DXA, hip and spine) | g/cm² | M | compare to preflight; the existing `BONE_DENSITY_CALCIUM` is a single value | Loss about 0.9%/month spine, 1.4-1.5%/month hip on 4-6 month ISS flights [S26, snippet] | 25 |
| `T_SCORE` | BMD T-score | SD | M (DXA report) | WHO: normal -1.0 or above; osteopenia -1.0 to -2.5; osteoporosis -2.5 or below [S22] | Fracture risk; recovery is partial, tibia still about -2.1% at 1 year after return [S28] | 24 |
| `GRIP_STRENGTH` | Grip strength | kg | M | low: men under 27, women under 16 (EWGSOP2) [S24] | Strength loss; calf strength about -24%, knee extensors about -10% in ISS crew [S27] | 26 |
| `WAIST_CIRCUMFERENCE` | Waist circumference | cm | M | - | Input for waist-to-height ratio | 23 |
| `WAIST_TO_HEIGHT_RATIO` | Waist-to-height ratio | ratio | D | about 0.5 cutoff (adults) [S25, secondary] | Central fat; needs no sex field | 23 |
| `BASAL_METABOLIC_RATE` | Basal metabolic rate (Mifflin-St Jeor) | kcal/day | D | ±10% accuracy [S19] | Energy planning; in-flight voluntary intake falls about 20% [S27, secondary] | 21 |
| `TOTAL_ENERGY_EXPENDITURE` | Total daily energy expenditure | kcal/day | D | BMR x activity factor [unverified factors] | Energy balance is the main nutrition problem under high exercise load [S32] | 22 |
| `PROTEIN_INTAKE` | Protein intake | g/kg/day | M (log) | NASA target not found [unsourced] | Muscle preservation | - |
| `ENERGY_INTAKE` | Energy intake | kcal/day | M (log) | compare to TDEE | Detects energy deficit | 22 |
| `VITAMIN_D` | Serum 25(OH)D | ng/mL | M (lab) | sufficiency commonly 20 or more [unverified] | Bone health; one ISS study used 400 IU/day supplements [S32] | rules |
| `CALCIUM_INTAKE` | Calcium intake | mg/day | M (log) | NASA target not found [unsourced] | Bone health, kidney stone risk | - |
| `URINE_CHEMISTRY` | Urine chemistry (stone-forming risk) | panel | M (lab) | no thresholds found | Urine chemistry changes in flight; stone rate higher in first year after return [S29, S30] | rules |

### Sleep, stress, cognition, radiation, vision

| Proposed key | Name | Unit | M/D | Typical range / reference | Why it matters for astronauts | Calc |
|---|---|---|---|---|---|---|
| `TIME_IN_BED` | Time in bed | h | M | - | Needed for sleep efficiency | 27 |
| `SLEEP_EFFICIENCY` | Sleep efficiency | % | D | about 85% or more (clinical convention) [unverified] | ISS crew get about 6-6.5 h of an 8.5 h opportunity [S39, S40] | 27 |
| `SLEEP_LATENCY` | Sleep latency | min | M | about 10-20 normal; over 30 often flagged [unverified] | Circadian disruption: about 16 sunrises per day [S41] | rules |
| `SLEEP_DEBT` | Cumulative sleep debt | h | D | no standard formula [design] | 6 h or less linked to lower vigilant attention [S40] | 28 |
| `HRV_RMSSD` | Heart rate variability (RMSSD) | ms | D (from RR intervals) | no verified 5-min normal range; use personal baseline [S50, S51] | Autonomic / stress marker | 29 |
| `PSS10` | Perceived Stress Scale | 0-40 | M (questionnaire) | bands 0-13 / 14-26 / 27-40 are widely used but not official [S45, S46] | Validated alternative to the 1-10 `STRESS_LEVEL` | 30 |
| `PVT_LAPSES` | Psychomotor Vigilance Test lapses | count | M (test) | lapse = response 500 ms or slower (10-min PVT); 355 ms for PVT-B [S47] | Sleep loss increases lapses [S40, S47] | 31 |
| `KSS` | Karolinska Sleepiness Scale | 1-9 | M | not verified in sources | Quick subjective sleepiness | - |
| `RADIATION_DOSE` | Cumulative effective radiation dose | mSv | M (dosimeter) | NASA career limit 600 mSv (all ages and sexes) [S33, S34]; ESA 1000 mSv [S35, secondary]. Calcule.md 11 covers a single mission exposure class | Cancer risk; ALARA principle | 32 |
| `SANS_OPTIC_DISC_EDEMA` | Optic disc edema (Frisén grade) | grade | M (ophthalmic exam) | 0 = none | SANS (Spaceflight-Associated Neuro-ocular Syndrome) [S49] | rules |
| `SANS_CHOROIDAL_FOLDS` | Choroidal / chorioretinal folds | yes/no | M (ophthalmic exam) | none | Found in 12 of 72 eyes (17%) in a NASA ISS study [S48] | rules |
| `SANS_GLOBE_FLATTENING` | Globe flattening / hyperopic shift | yes/no, diopters | M (imaging, refraction) | none | SANS findings [S49] | rules |

### Requested but not covered by the research `[unsourced]`

The researchers did not find sources for these. They are listed so they are not forgotten. Do not add thresholds until a source is found.

| Proposed key | Name | Unit | Note |
|---|---|---|---|
| `HYDRATION` | Hydration status (e.g. urine specific gravity or daily fluid intake) | - / mL | Related to fluid shift [S1] and kidney stone risk [S29], but no hydration thresholds were found |
| `CORTISOL` | Cortisol (stress hormone) | lab units | No spaceflight source or range found |
| `INTRACRANIAL_PRESSURE` | Intracranial pressure indicators | - | Not researched; SANS eye findings (above) are the indicators that were sourced |
| `IMMUNE_MARKERS` | Immune markers (e.g. white cell count) | lab units | The immune system was not covered by any researcher |

## Calculations 14-35

Calculations 14-35 are implemented in [calculations.py](calculations.py) with the same numbers in their docstrings.

### 14. Mean arterial pressure (MAP)

- **Inputs:** `SYSTOLIC_BLOOD_PRESSURE`, `DIASTOLIC_BLOOD_PRESSURE`
- **Formula:** `map = DIASTOLIC_BLOOD_PRESSURE + (SYSTOLIC_BLOOD_PRESSURE - DIASTOLIC_BLOOD_PRESSURE) / 3`
- **Output:** mmHg, one decimal. Typical about 70-100 [unverified]

### 15. Pulse pressure

- **Inputs:** `SYSTOLIC_BLOOD_PRESSURE`, `DIASTOLIC_BLOOD_PRESSURE`
- **Formula:** `pulse_pressure = SYSTOLIC_BLOOD_PRESSURE - DIASTOLIC_BLOOD_PRESSURE`
- **Output:** mmHg. Typical about 40-60 [unverified]. Always positive, because the input already checks systolic > diastolic.

### 16. Maximum heart rate (Tanaka) and percentage of maximum

- **Inputs:** `AGE`, a heart rate during exercise
- **Formula:** `max_heart_rate = 208 - 0.7 * AGE` [S18, unverified]; `percent_max_hr = pulse / max_heart_rate * 100`
- **Note:** an alternative to Calcule.md 13 (`220 - AGE`). That formula is reported to be less accurate at older ages. Pick one (see Open decisions).
- **Use:** NASA aerobic guidance is at least 160 min/week at an average above 75% of peak HR [S8].

### 17. Heart rate recovery

- **Inputs:** HR at end of exercise, HR 1 minute later
- **Formula:** `recovery = final_exercise_pulse - pulse_after_1_min`
- **Threshold:** 12 bpm or less is abnormal [unverified]

### 18. VO2max compared with the preflight value

- **Inputs:** `VO2_MAX` now, `VO2_MAX` preflight (baseline)
- **Formula:** `vo2_percent = VO2_MAX / vo2_max_preflight * 100`
- **Threshold:** keep at or above 80% of preflight (NASA-STD-3001 Vol 1, from a search snippet; confirm in the standard)
- **Note:** needs a stored baseline per astronaut. The database currently has one row per astronaut and no history.

### 19. Orthostatic response

- **Inputs:** SBP and HR supine, SBP and HR after standing (10 min)
- **Formula:** `delta_systolic = systolic_standing - systolic_supine`; `delta_heart_rate = hr_standing - hr_supine`
- **Threshold:** orthostatic intolerance = symptoms plus a BP drop or HR rise. Exact cutoffs vary between sources and are not verified. Confirm against NASA-STD-3001 / the technical brief [S3].

### 20. FFMI (fat-free mass index)

- **Inputs:** lean mass (Calcule.md 3), `HEIGHT`
- **Formula:** `ffmi = lean_mass_kg / (height_m ** 2)`; normalised: `ffmi_norm = ffmi + 6.1 * (1.8 - height_m)` (Kouri 1995) [S21]
- **Needs:** `SEX` to choose the range

### 21. Basal metabolic rate (Mifflin-St Jeor)

- **Inputs:** `BODY_WEIGHT`, `HEIGHT` (cm), `AGE`, `SEX`
- **Formula:** `bmr = 10 * BODY_WEIGHT + 6.25 * HEIGHT - 5 * AGE + s`, where `s = +5` for men and `s = -161` for women [S19, S20]
- **Note:** about ±10% accuracy; less reliable with high muscle mass [S19]. Cannot be computed until `SEX` exists.

### 22. Total daily energy expenditure (TDEE) and energy balance

- **Inputs:** `bmr` (calculation 21), activity level, `ENERGY_INTAKE`
- **Formula:** `tdee = bmr * activity_factor`; `balance = ENERGY_INTAKE - tdee`
- **Activity factors (common, [unverified]):** 1.2 sedentary, 1.375 light, 1.55 moderate, 1.725 very active, 1.9 extra active
- **Note:** in-flight exercise load differs from Earth activity categories. The medical/nutrition team should pick the factor.

### 23. Waist-to-height ratio

- **Inputs:** `WAIST_CIRCUMFERENCE`, `HEIGHT` (both cm)
- **Formula:** `whtr = WAIST_CIRCUMFERENCE / HEIGHT`
- **Threshold:** about 0.5 for adults [S25, secondary]

### 24. Bone density category (T-score)

- **Inputs:** `T_SCORE`
- **Thresholds (WHO) [S22]:** -1.0 or above normal; below -1.0 and above -2.5 osteopenia; -2.5 or below osteoporosis

### 25. Bone loss rate

- **Inputs:** `BONE_MINERAL_DENSITY` now and preflight, months in flight
- **Formula:** `loss_pct_per_month = (bmd_preflight - bmd_now) / bmd_preflight * 100 / months`
- **Reference:** reported averages about 0.9%/month spine and 1.4-1.5%/month hip [S26, snippet]. These are averages, not limits.

### 26. Grip strength

- **Inputs:** `GRIP_STRENGTH`, `SEX`
- **Threshold (EWGSOP2) [S24]:** low if men under 27 kg, women under 16 kg

### 27. Sleep efficiency

- **Inputs:** `SLEEP_HOURS` (total sleep time), `TIME_IN_BED`
- **Formula:** `efficiency = SLEEP_HOURS / TIME_IN_BED * 100`
- **Threshold:** about 85% or more is usual for healthy adults [unverified]

### 28. Cumulative sleep debt

- **Inputs:** daily `SLEEP_HOURS` over a window, `AGE`
- **Formula:** `debt = sum(recommended(AGE) - hours_per_day for each day in window)`
- **`recommended(AGE)` (NSF) [S37]:** 18-64 years: 7-9 h; 65+ years: 7-8 h. Use the lower bound (7 h) as the minimum; AASM also recommends at least 7 h for adults [unverified, secondary].
- **Note:** no standard formula exists; window length (e.g. 7 days) is a [design] choice. This extends Calcule.md 9 ("confirm the exact value").

### 29. HRV (RMSSD)

- **Inputs:** RR intervals (ms) from ECG / wearable
- **Formula:** `rmssd = sqrt(mean((rr[i+1] - rr[i]) ** 2))` (Task Force 1996) [S51]
- **Note:** no verified normal range for 5-minute RMSSD. Compare each astronaut to their own baseline [design].

### 30. PSS-10 score

- **Inputs:** 10 answers, each 0-4
- **Formula:** reverse-score items 4, 5, 7 and 8 (`4 - answer`), then sum all 10 → 0-40
- **Bands (not official) [S45, S46]:** 0-13 low, 14-26 moderate, 27-40 high

### 31. PVT lapses

- **Inputs:** reaction times from a PVT session (ms)
- **Formula:** `lapses = count(rt >= 500)` for the 10-min PVT; use 355 ms for the brief PVT-B [S47]
- **Use:** compare with the astronaut's baseline; rising lapses indicate sleep loss [S40, S47]

### 32. Cumulative radiation dose and percentage of the limit

- **Inputs:** per-mission effective doses (mSv)
- **Formula:** `career_dose = sum(mission_doses)`; `limit_pct = career_dose / 600 * 100`
- **Limit:** NASA career limit 600 mSv effective dose [S33, S34]. NASA calls the value approximate; its adoption date is reported as 2021 or 2022. ESA uses 1000 mSv [S35, secondary].

### 33. Stress level (1-10 scale)

- **Inputs:** `STRESS_LEVEL`
- **Proposed bands [design, no official source]:** 1-3 low, 4-6 moderate, 7-10 high
- **Note:** no official source maps a 1-10 self-rating to bands [S46]. This proposal extends Calcule.md 10 until the medical team decides. Consider `PSS10` (calculation 30) as a validated alternative.

### 34. Blood glucose category, hypoglycemia levels

- **Inputs:** `BLOOD_GLUCOSE`
- **Thresholds (ADA) [S16]:** Level 1 hypoglycemia: under 70 and 54 or above mg/dL; Level 2: under 54 mg/dL. Extends Calcule.md 8.

### 35. Hypertensive crisis

- **Inputs:** `SYSTOLIC_BLOOD_PRESSURE`, `DIASTOLIC_BLOOD_PRESSURE`, symptoms flag
- **Threshold (AHA) [S14, S15]:** above 180 systolic and/or above 120 diastolic. With symptoms (chest pain, shortness of breath, weakness, vision or speech change) it is an emergency. Extends Calcule.md 6.
- **Note:** a 2025 AHA/ACC guideline exists; one secondary source gives stage 2 as 140 or more / 90 or more. Not verified against the official text.

## Influence map

Which body part or system each variable affects, and when it matters. Researchers did not cover the launch phase, so launch is rarely marked.

**Legend:**
- **●** = influence documented in a source found by the researchers.
- **○** = plausible link, own judgment, `[unsourced]`. Confirm before relying on it.
- Blank = no relevant link expected or found.
- Phase codes: **L** launch, **A** adaptation to microgravity (first days to weeks), **D** long-duration flight (months), **R** return to gravity and recovery after landing, **\*** all phases.

| Variable | Heart & vessels | Brain & nervous system | Muscles | Bones | Eyes | Kidneys & fluids | Metabolism & hormones | Blood | Immune | Sleep & circadian | When / note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SYSTOLIC_BLOOD_PRESSURE` / `DIASTOLIC_BLOOD_PRESSURE` | ● A,R | ○ R | | | ○ \* | ● A | | | | | Fluid shift in A [S1]; drop on standing after landing [S1, S4] |
| `MEAN_ARTERIAL_PRESSURE`, `PULSE_PRESSURE` | ● A,R | | | | | ● A | | | | | Pulse pressure tracks stroke volume, main factor in post-flight intolerance [S4] |
| `AVERAGE_HEART_RATE` / `RESTING_PULSE` | ● R | ● R | | | | | | | | ○ \* | HR rise on standing after landing [S1, S6]; autonomic control [S6] |
| `ORTHOSTATIC_TEST` | ● R | ● R | | | | ● R | | | | | About 30% of crew after landing; baroreflex impaired [S4] |
| `VO2_MAX`, `MAX_HEART_RATE`, `HEART_RATE_RECOVERY` | ● D,R | | ● D | | | | | | | | VO2max falls in long flights [S7, S10] |
| `HEMOGLOBIN` / `HEMATOCRIT` | ○ D | | | | | ● A | | ● A,D,R | | | Red cell mass falls after about 9 days; recovery 30 days to 3-4 months [S11, S12] |
| `BLOOD_GLUCOSE`, `HBA1C` | ○ \* | ○ \* | ○ \* | | | | ● \* | | | | Insulin resistance in flight was not found in sources |
| `BODY_MASS_INDEX`, `BODY_WEIGHT` | ○ \* | | ● D | | | | ● D | | | | Intake falls about 20% in flight [S27] |
| `MUSCLE_MASS_PERCENTAGE`, `FFMI`, `GRIP_STRENGTH` | | | ● D,R | ● D | | | ● D | | | | Calf -24%, knee extensors -10% strength [S27]; postural muscles worst |
| `BODY_FAT_PERCENTAGE`, `WAIST_TO_HEIGHT_RATIO` | ○ \* | | | | | | ● D | | | | Energy balance [S32] |
| `BONE_MINERAL_DENSITY`, `T_SCORE`, `BONE_DENSITY_CALCIUM` | | | | ● D,R | | ● R | | | | | 0.9-1.5%/month loss [S26]; partial recovery at 1 year [S28]; stone risk after return [S29] |
| `BASAL_METABOLIC_RATE`, `TOTAL_ENERGY_EXPENDITURE`, `ENERGY_INTAKE`, `PROTEIN_INTAKE` | | | ● D | ○ D | | | ● D | | | | Energy deficit under high exercise load [S32] |
| `VITAMIN_D`, `CALCIUM_INTAKE` | | | | ● D | | ○ D | ● D | | ○ \* | | ISS vitamin D supplementation [S32] |
| `URINE_CHEMISTRY` | | | | ● D | | ● D,R | | | | | Urine chemistry changes; stones more frequent in first year after return [S29, S30] |
| `SLEEP_HOURS`, `SLEEP_EFFICIENCY`, `SLEEP_LATENCY`, `SLEEP_DEBT` | | ● D | | | | | ○ \* | | ○ \* | ● \* | About 6-6.5 h on ISS; 6 h or less lowers vigilance [S39, S40] |
| `STRESS_LEVEL`, `PSS10` | ○ \* | ● D | | | | | ○ \* | | ○ \* | ● D | Sleep deficiency linked to higher stress [S40] |
| `HRV_RMSSD` | ● \* | ● \* | | | | | | | | ○ \* | Autonomic balance; baroreflex changes after flight [S4, S6] |
| `PVT_LAPSES`, `KSS` | | ● D | | | | | | | | ● D | Sleep loss raises lapses [S40, S47] |
| `RADIATION_DOSE`, `MISSION_RADIATION_LEVEL` | ○ D | ○ D | | | ○ D | | | ○ D | ○ D | | Limit is based on cancer risk (3% benchmark) [S33, S34]; organ effects not researched |
| `SANS_*` (eye findings) | | ○ D | | | ● D,R | ○ A | | | | | Disc edema, folds in 17% of eyes, hyperopic shift [S48, S49] |
| `AGE` | ○ \* | ● \* | ○ \* | ○ \* | | | ● \* | | | ● \* | Sleep need by age [S37]; BMR [S19]; HRV falls with age [S50] |
| `HYDRATION` [unsourced] | ○ A,R | | | | | ○ \* | | | | | Linked conceptually to fluid shift and stone risk; no thresholds |

## Recommendation system

### Status levels

| Level | Code | Meaning |
|---|---|---|
| 0 | `OK` | Inside the reference range |
| 1 | `WATCH` | Outside the ideal range or trending badly; recheck and self-correct |
| 2 | `ACTION` | Clear problem; start a countermeasure and inform the medical team |
| 3 | `URGENT` | Possible emergency; contact the flight surgeon now |
| - | `UNKNOWN` | Value missing or out of input limits; never treated as `OK` [design] |

### How a status is computed

1. Validate the input against `CHARACTERISTIC_DEFINITIONS` in Caracteristici.py. Values outside the allowed limits give `UNKNOWN` (data error), not a clinical status.
2. Compute derived values (Calcule.md 1-13 and calculations 14-35 in this file).
3. Evaluate every rule below. A rule is `variable + condition → status + body system + recommendation`.
4. Rules can use absolute thresholds or a change from the astronaut's preflight baseline. Baseline rules need history storage (see Open decisions).
5. Each variable gets the highest status among its matching rules.

### Rules table

`Protects` names the body system column in the [Influence map](#influence-map). Thresholds marked `[design]` are project proposals with no medical source.

| ID | Variable | Condition | Status | Protects | Recommended action | Source |
|---|---|---|---|---|---|---|
| CV-1 | BP | SBP > 180 or DBP > 120 **with** symptoms | URGENT | Heart & vessels, Brain | Emergency medical response | [S14, S15] |
| CV-2 | BP | SBP > 180 or DBP > 120, no symptoms | ACTION | Heart & vessels | Rest, recheck, prompt contact with flight surgeon | [S14, S15] |
| CV-3 | BP | SBP ≥ 130 or DBP ≥ 80 (calc 6 "high") | WATCH | Heart & vessels | Recheck at rest; report trend to medical team | calc 6 |
| CV-4 | BP | SBP < 90 or DBP < 60 (calc 6 "low") | WATCH | Heart & vessels, Kidneys & fluids | Recheck; if near return, see CV-6 | calc 6 |
| CV-5 | Resting HR | < 60 or > 100 at rest | WATCH | Heart & vessels | Recheck at rest; medical review if persistent | calc 7 |
| CV-6 | Orthostatic test | symptoms + BP drop or HR rise on standing | ACTION | Heart & vessels, Brain | Fluid and salt loading before reentry (most established countermeasure); medical review | [S1, S3] |
| CV-7 | VO2max | < 80% of preflight | ACTION | Heart & vessels, Muscles | Aerobic exercise ≥ 160 min/week at > 75% peak HR; high-intensity (Sprint) protocol is an option | [S8, S9], NASA-STD-3001 snippet |
| CV-8 | VO2max | 80-90% of preflight | WATCH | Heart & vessels | Same exercise target; recheck sooner | [design] |
| BL-1 | Hemoglobin / hematocrit | below lab reference | WATCH | Blood | Medical follow-up; recheck after return (recovery 30 days to 3-4 months) | [S11, S12], thresholds open |
| MT-1 | Glucose | < 54 mg/dL | URGENT | Metabolism, Brain | Treat immediately per medical protocol | [S16] |
| MT-2 | Glucose | 54-69 mg/dL | ACTION | Metabolism, Brain | Treat per medical protocol; recheck | [S16] |
| MT-3 | Glucose (fasting) | 100-125 mg/dL | WATCH | Metabolism | Nutrition review; recheck fasting | calc 8 |
| MT-4 | Glucose (fasting) | ≥ 126 mg/dL | ACTION | Metabolism | Medical follow-up | calc 8 |
| MT-5 | HbA1c | 5.7-6.4% / ≥ 6.5% | WATCH / ACTION | Metabolism | Medical follow-up; nutrition review | [unverified] |
| MT-6 | Energy balance | intake < TDEE for several days | WATCH | Metabolism, Muscles | Nutrition plan to close the deficit | [S32]; day count [design] |
| MT-7 | BMI | < 18.5 / ≥ 30 | WATCH | Metabolism, Muscles | Nutrition and exercise review | calc 5 |
| MT-8 | Body fat % | below essential fat (men 2-5, women 10-13) | ACTION | Metabolism | Nutrition review, medical follow-up | [S23] |
| MT-9 | Body fat % / WHtR | men ≥ 25, women ≥ 32 / WHtR ≥ 0.5 | WATCH | Metabolism, Heart & vessels | Nutrition and exercise review | [S23, S25] |
| MS-1 | Muscle % / FFMI | drop from preflight above X% | WATCH | Muscles | Resistance exercise (ARED) | [S31]; X [design] |
| MS-2 | Grip strength | men < 27 kg, women < 16 kg | ACTION | Muscles | Resistance exercise; medical review | [S24, S31] |
| BN-1 | Bone loss rate | > 1.5%/month | WATCH | Bones | More resistance exercise; in-flight deadlifting linked to better recovery | [S26, S28]; cutoff [design] |
| BN-2 | T-score | below -1.0 and above -2.5 | WATCH | Bones | Resistance exercise; nutrition (vitamin D, calcium) review | [S22] |
| BN-3 | T-score | ≤ -2.5 | ACTION | Bones | Medical evaluation; any drug only under medical supervision | [S22] |
| BN-4 | Vitamin D | < 20 ng/mL | WATCH | Bones | Supplementation as decided by the medical team | [unverified], [S32] |
| KD-1 | Urine chemistry / return phase | after return, first year | WATCH | Kidneys & fluids, Bones | Monitor urine chemistry for stone risk | [S29, S30] |
| SL-1 | Sleep hours | < recommended(age) (7 h) | WATCH | Sleep, Brain | Fixed sleep/wake schedule; sleep-promoting lighting | [S37, S42, S44] |
| SL-2 | Sleep hours | ≤ 6 h, or sleep debt over Y h | ACTION | Sleep, Brain | As SL-1, plus workload review; medication only after behavioural options | [S40, S43]; Y [design] |
| SL-3 | Sleep efficiency / latency | < 85% / > 30 min | WATCH | Sleep | Sleep hygiene; scheduled lighting | [unverified] |
| CG-1 | PVT lapses | rising vs baseline | WATCH (ACTION if large) | Brain, Sleep | Review sleep and workload | [S40, S47]; size [design] |
| PS-1 | Stress 1-10 | 4-6 | WATCH | Brain | Stress management; track trend | [design] |
| PS-2 | Stress 1-10 / PSS-10 | 7-10 / 27-40 | ACTION | Brain, Sleep | Psychological support | [design], [S45, S46] |
| PS-3 | HRV | sustained drop vs baseline | WATCH | Heart & vessels, Brain | Check sleep and stress rules | [design] |
| RD-1 | Radiation | ≥ 50% of career limit | WATCH | Blood, Immune, all | ALARA: minimise further exposure | [S34]; 50% [design] |
| RD-2 | Radiation | ≥ 80% of career limit | ACTION | all | Mission planning review with medical team | 80% [design] |
| RD-3 | Radiation | ≥ 100% (600 mSv NASA) | URGENT | all | Limit reached; no further exposure without medical/program decision. Shielding / storm shelter during solar events | [S33, S34] |
| EY-1 | SANS findings | any new disc edema, folds, globe flattening | ACTION | Eyes | Ophthalmic exam follow-up | [S48, S49] |
| EY-2 | SANS findings | grade worsens between exams | URGENT | Eyes | Immediate ophthalmic / medical review | [design] |

### How rules combine [design]

These are software design choices, not medical rules. The medical team should review them.

1. **Per system:** a body system's status is the highest status of the rules that protect it.
2. **Escalation within a system:** 3 or more `WATCH` rules on the same system raise that system to `ACTION`.
3. **Multi-system:** `ACTION` on 2 or more systems sets an overall "multi-system review" flag for the flight surgeon.
4. **Known combinations:**
   - Sleep deficit (SL-1/SL-2) together with high stress (PS-2): raise both by one level. Sleep deficiency and stress are linked on ISS missions [S40].
   - Low BP (CV-4) together with high resting HR (CV-5) in the return phase: treat as CV-6 (`ACTION`).
5. **Overall status** = highest system status. `URGENT` is never lowered by combination.
6. **Missing data:** `UNKNOWN` does not count as `OK`. A required input that is missing is listed as "measure this".

### Priority and ordering of recommendations [design]

1. Sort by status: `URGENT` → `ACTION` → `WATCH`.
2. Within the same status, rules relevant to the current mission phase (A / D / R) come first.
3. Then by system order: Heart & vessels, Brain, Eyes, Blood, Metabolism, Bones, Muscles, Kidneys & fluids, Sleep, Immune.
4. Remove duplicate actions (e.g. "resistance exercise" from MS-1 and BN-1 appears once, listing both systems it protects).
5. Every recommendation shows its rule ID, the systems it protects, and the source tag.

### Implementation sketch (documentation only)

How this could later sit next to `CHARACTERISTIC_DEFINITIONS` in Caracteristici.py. Not code to copy as is.

```python
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Callable

class Status(IntEnum):
    OK = 0
    WATCH = 1
    ACTION = 2
    URGENT = 3

class BodySystem(Enum):      # columns of the Influence map
    HEART_VESSELS = "Heart & vessels"
    BRAIN = "Brain & nervous system"
    MUSCLES = "Muscles"
    BONES = "Bones"
    EYES = "Eyes"
    KIDNEYS_FLUIDS = "Kidneys & fluids"
    METABOLISM = "Metabolism & hormones"
    BLOOD = "Blood"
    IMMUNE = "Immune"
    SLEEP = "Sleep & circadian"

@dataclass(frozen=True)
class Rule:
    id: str                              # "CV-1"
    condition: Callable[[dict], bool]    # receives all values (inputs + derived)
    status: Status
    protects: tuple[BodySystem, ...]
    action: str
    source: str                          # "[S14, S15]" or "[design]"

RULES: tuple[Rule, ...] = (
    Rule("CV-2", lambda v: v["SYSTOLIC_BLOOD_PRESSURE"] > 180 or v["DIASTOLIC_BLOOD_PRESSURE"] > 120,
         Status.ACTION, (BodySystem.HEART_VESSELS,), "Rest, recheck, contact flight surgeon", "[S14, S15]"),
    # ... one entry per row of the rules table
)

def evaluate(values: dict) -> list[Rule]:
    """Return the matching rules; does not change `values`."""
    return [r for r in RULES if r.condition(values)]

def status_by_system(matches: list[Rule]) -> dict[BodySystem, Status]:
    """Highest status per system, then escalation rule 2 (3+ WATCH -> ACTION)."""
    ...

def ordered_recommendations(matches: list[Rule], phase: str) -> list[Rule]:
    """Sort by status desc, phase relevance, system order; dedupe actions."""
    ...
```

Notes for the implementation:
- Rule conditions must skip (return `UNKNOWN`) when an input they need is missing, instead of raising.
- Thresholds should live in one table (constants), not inside lambdas, so the medical team can review them in one place.
- Keep results immutable: `evaluate` returns new objects and never edits the input values.

## Open decisions (additional)

These extend the open decisions in Calcule.md (which already covers BMI measured or derived, the stress scale, and the README typo).

1. Add a `SEX` field? Calculations 20, 21, 26 and the body fat / T-score ranges cannot work without it.
2. Max heart rate: keep `220 - AGE` (Calcule.md 13) or switch to Tanaka `208 - 0.7 * AGE` (calculation 16)?
3. History storage: the database has one row per astronaut. Baseline and trend rules (VO2max vs preflight, bone loss rate, sleep debt, PVT, HRV) need dated measurements and a preflight baseline.
4. Which candidate variables are added first? Most need new hardware or lab tests (DXA, VO2max test, ophthalmic exam, dosimeter).
5. Mission phase input (adaptation / long-duration / return): needed to order recommendations and apply return-phase rules (CV-6, KD-1).
6. All `[design]` thresholds (stress 1-10 bands, escalation counts, 50%/80% radiation steps, X% muscle drop, Y h sleep debt, VO2max 90% watch) need a decision by the medical team.
7. Conflicts found by the researchers, to resolve with the medical team:
    - Post-flight orthostatic intolerance: about 30% pooled [S4] vs 30% to over 80% depending on mission length (2025 review); sources disagree on whether duration matters.
    - Space anemia: hemoconcentration and low EPO vs hemolysis [S11]; clinical significance disputed.
    - In-flight exercise time: "about 2.5 h/day" is often quoted but a study of 46 astronauts found about 600 min/week (about 85 min/day) [S31].
    - NASA 600 mSv limit: adoption date reported as 2021 or 2022.
8. Not researched or not found, needs a source before use: hydration, cortisol, intracranial pressure, immune markers, LDL cholesterol, protein / calcium / vitamin D targets for astronauts, launch-phase effects, in-flight insulin resistance.

## Sources

Researchers could not open several primary pages (403 or cookie walls). Values taken from search snippets or secondary sites are marked in the text. Check each against the primary source before implementation.

**Cardiovascular and metabolic**
- [S1] NASA evidence report, orthostatic intolerance on re-exposure to gravity: https://ntrs.nasa.gov/api/citations/20150007319/downloads/20150007319.pdf
- [S2] NASA Human Research Roadmap, cardiovascular risk evidence report 2022: https://humanresearchroadmap.nasa.gov/Evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf
- [S3] NASA OCHMO technical brief, orthostatic intolerance: https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-019-orthostatic-intolerance.pdf
- [S4] Orthostatic intolerance in spaceflight, systematic review and meta-analysis (2026): https://www.sciencedirect.com/science/article/pii/S0094576526003346
- [S5] Review of microgravity effects on cardiovascular and nervous systems: https://pmc.ncbi.nlm.nih.gov/articles/PMC12575774/
- [S6] Cardiovascular autonomic responses and orthostatic intolerance in astronauts: https://pmc.ncbi.nlm.nih.gov/articles/PMC9018660/
- [S7] Aerobic capacity after long-duration ISS missions: https://ntrs.nasa.gov/citations/20100037247
- [S8] Exercise intensity and time vs VO2peak in spaceflight: https://ntrs.nasa.gov/citations/20140003747
- [S9] NASA Sprint study, high-intensity training in spaceflight: https://www.nature.com/articles/s41526-020-00111-x
- [S10] Peak oxygen uptake after long-duration spaceflight: https://journals.physiology.org/doi/full/10.1152/japplphysiol.01251.2013
- [S11] Hemolysis and anemia in long-duration spaceflight (Nature Medicine 2021): https://www.nature.com/articles/s41591-021-01637-7
- [S12] Control of red blood cell mass during spaceflight: https://pubmed.ncbi.nlm.nih.gov/11540296/
- [S13] Simulated microgravity and hematological biomarkers, meta-analysis (2026): https://link.springer.com/article/10.1186/s42269-026-01407-w
- [S14] AHA, high blood pressure top 10: https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/high-bp-top-10
- [S15] AHA, when to call 911 for high blood pressure: https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/when-to-call-911-for-high-blood-pressure
- [S16] ADA Standards of Care 2025, Section 6 (glycemic goals, hypoglycemia): https://diabetesjournals.org/care/article/48/Supplement_1/S128/157561/6-Glycemic-Goals-and-Hypoglycemia-Standards-of
- [S17] ADA Standards of Care 2026, Section 16: https://diabetesjournals.org/care/article/49/Supplement_1/S339/163925/16-Diabetes-Care-in-the-Hospital-Standards-of-Care
- [S18] Tanaka et al. 2001, age-predicted max heart rate (not opened): https://pubmed.ncbi.nlm.nih.gov/11153730/

**Musculoskeletal and body composition**
- [S19] Mifflin-St Jeor BMR (secondary): https://inchcalculator.com/bmr-calculator
- [S20] BMR guide (secondary): https://calcfyi.com/guide/health-science/understanding-bmr/
- [S21] FFMI and normalized FFMI (secondary): https://inchcalculator.com/ffmi-calculator
- [S22] WHO T-score categories: https://pmc.ncbi.nlm.nih.gov/articles/PMC2600106/table/tbl1
- [S23] ACE body fat categories (secondary): https://www.acefitness.org/about-ace/press-room/in-the-news/8602/body-fat-percentage-charting-averages-in-men-and-women-very-well-health/
- [S24] EWGSOP2 grip strength cut-points: https://pmc.ncbi.nlm.nih.gov/articles/PMC9879709/table/TB2
- [S25] Waist-to-height ratio (secondary): https://www.metabolicum.com
- [S26] Lang et al. 2004, bone loss on ISS (snippet only): https://pubmed.ncbi.nlm.nih.gov/15125798/
- [S27] Roberts et al. 2025, musculoskeletal responses to spaceflight: https://eprints.soton.ac.uk/507468/1/roberts-et-al-2025-musculoskeletal-responses-to-spaceflight-mechanisms-countermeasures-and-key-gaps.pdf
- [S28] TBone study, bone recovery after spaceflight (2022): https://sciencedaily.com/releases/2022/06/220630134845.htm
- [S29] NASA HRP renal stone risk: https://ntrs.nasa.gov/citations/20160013663
- [S30] NASA HRP renal risk update 2023: https://ntrs.nasa.gov/api/citations/20230015722/downloads/RenalPanel-4-HRP%20risk.pdf
- [S31] NASA ISS exercise countermeasures: https://ntrs.nasa.gov/api/citations/20160008094/downloads/20160008094.pdf
- [S32] NASA, Human Adaptation to Spaceflight: The Role of Food and Nutrition (2021): https://www.nasa.gov/sites/default/files/atoms/files/human_adaptation_2021_final.pdf

**Sleep, stress, cognition, radiation, vision**
- [S33] NASA-STD-3001 Vol 1 Rev C, compliance matrix: https://www.nasa.gov/wp-content/uploads/2025/01/nasa-std-3001-vol-1-appendix-d.pdf
- [S34] NASA OCHMO technical brief, radiation protection: https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-020-radiation-protection.pdf
- [S35] National Academies 2021, space radiation and astronaut health: https://www.nationalacademies.org/read/26155/chapter/5
- [S36] Mars mission dose estimates (arXiv): https://arxiv.org/pdf/2409.02001
- [S37] National Sleep Foundation, sleep duration recommendations: https://www.thensf.org/sleep-duration-recommendations/
- [S38] NSF recommendations 10-year review (Sleep Health 2026): https://www.sleephealthjournal.org/article/S2352-7218(26)00106-3/fulltext
- [S39] NASA sleep evidence report: https://humanresearchroadmap.nasa.gov/Evidence/reports/Sleep.pdf
- [S40] Sleep deficiency on 6-month ISS missions (Sleep 2022): https://academic.oup.com/sleep/article/45/3/zsac006/6505235
- [S41] Circadian misalignment and sleep in spaceflight (npj Microgravity 2015): https://www.nature.com/articles/npjmgrav201519
- [S42] NASA sleep accommodations technical brief: https://www.nasa.gov/wp-content/uploads/2023/03/sleep-accomodations-technical-brief-ochmo.pdf
- [S43] NASA OCHMO technical brief TB-041, sleep: https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-041-sleep-accommodations.pdf
- [S44] NASA, seven ways astronauts improve sleep: https://www.nasa.gov/humans-in-space/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/
- [S45] PSS-10 scoring bands (secondary): https://www.mentalyc.com/blog/perceived-stress-scale-pss-10
- [S46] PSS caveat, no official cut-offs (secondary): https://www.tacklit.com/assessments/perceived-stress-scale-pss
- [S47] Basner et al. 2011, brief PVT validity: https://www.med.upenn.edu/uep/assets/user-content/documents/Basner2011-ValidityandsensitivityofabriefPVT.pdf
- [S48] NASA study, chorioretinal folds in spaceflight: https://ntrs.nasa.gov/api/citations/20230002241/downloads/CRFerguson_ChorioretinalFoldsSpaceflight_ArticleFile_Revision_CLEAN.pdf
- [S49] SANS review (npj Microgravity): https://link.springer.com/10.1038/s41526-020-0097-9
- [S50] Population HRV / RMSSD by age (secondary for thresholds): https://pmc.ncbi.nlm.nih.gov/articles/PMC7734556
- [S51] Task Force of the ESC/NASPE 1996, Heart rate variability standards, European Heart Journal 17:354-381 (citation only, not opened)
