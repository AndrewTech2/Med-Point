/* -----------------------------------
   Med-Point | graph categories
   One source of truth for how metrics (Characteristic names used as keys in
   health_history.js and in the recommendations JSON) are grouped. Used by
   filters.js (category buttons) and recommendations_panel.js (click to filter).
   Cards without a data-metric count as "other" and show only under All.
   ----------------------------------- */

(function defineMetricCategories() {
    const CATEGORIES = Object.freeze([
        Object.freeze({
            key: "cardiovascular",
            label: "Cardiovascular",
            metrics: Object.freeze([
                "AVERAGE_HEART_RATE",
                "SYSTOLIC_BLOOD_PRESSURE",
                "DIASTOLIC_BLOOD_PRESSURE",
                "VO2_MAX",
                "HEART_RATE_RECOVERY"
            ])
        }),
        Object.freeze({
            key: "metabolic",
            label: "Metabolic",
            metrics: Object.freeze(["BLOOD_GLUCOSE", "BODY_MASS_INDEX", "BODY_FAT_PERCENTAGE"])
        }),
        Object.freeze({
            key: "musculoskeletal",
            label: "Muscles & bones",
            metrics: Object.freeze(["MUSCLE_MASS_PERCENTAGE", "BONE_DENSITY_CALCIUM"])
        }),
        Object.freeze({
            key: "sleep_stress",
            label: "Sleep & stress",
            metrics: Object.freeze(["SLEEP_HOURS", "STRESS_LEVEL"])
        }),
        Object.freeze({
            key: "environment",
            label: "Radiation",
            metrics: Object.freeze(["MISSION_RADIATION_LEVEL"])
        }),
        Object.freeze({
            key: "profile",
            label: "Body profile",
            metrics: Object.freeze(["BODY_WEIGHT", "HEIGHT", "AGE"])
        })
    ]);

    const BY_METRIC = Object.freeze(Object.fromEntries(
        CATEGORIES.flatMap(category => category.metrics.map(metric => [metric, category.key]))
    ));

    // Category key of a metric, or null when it belongs to none.
    function categoryOf(metricKey) {
        return Object.prototype.hasOwnProperty.call(BY_METRIC, metricKey)
            ? BY_METRIC[metricKey]
            : null;
    }

    function labelOf(categoryKey) {
        const found = CATEGORIES.find(category => category.key === categoryKey);
        return found ? found.label : null;
    }

    window.MED_POINT_CATEGORIES = CATEGORIES;
    window.MedPointCategories = Object.freeze({ categoryOf, labelOf, all: CATEGORIES });
})();
