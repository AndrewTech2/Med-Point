/* -----------------------------------
   Med-Point | dashboard interactions
   ----------------------------------- */

// Wires a button to a full-screen slide-in page with a back button.
function setupSlidePage({ openId, pageId, backId }) {
    const openButton = document.getElementById(openId);
    const page = document.getElementById(pageId);
    const backButton = document.getElementById(backId);

    if (!page) return;

    // The panel that grows into the full page, and back again.
    const source = openButton?.closest(".panel") || openButton;

    // Stagger order for the content that fades in after the zoom.
    page.querySelectorAll(
        ".eyebrow, h1, .colleagues-detail-intro, .crew-card, .graph-card"
    ).forEach((element, index) => element.style.setProperty("--i", index));

    // Places the page's starting window exactly over the source panel.
    function matchSource() {
        if (!source) return;

        const rect = source.getBoundingClientRect();

        page.style.setProperty("--from-top", `${Math.max(0, rect.top)}px`);
        page.style.setProperty("--from-left", `${Math.max(0, rect.left)}px`);
        page.style.setProperty("--from-right", `${Math.max(0, window.innerWidth - rect.right)}px`);
        page.style.setProperty("--from-bottom", `${Math.max(0, window.innerHeight - rect.bottom)}px`);
    }

    function open() {
        matchSource();
        page.scrollTop = 0;
        page.removeAttribute("inert");
        page.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
        document.body.classList.add("page-open");

        // Let the starting window paint before growing it.
        void page.offsetWidth;
        requestAnimationFrame(() => {
            page.classList.add("is-open");
        });

        backButton?.focus({ preventScroll: true });
    }

    function close() {
        matchSource();
        page.classList.remove("is-open");
        page.setAttribute("aria-hidden", "true");
        page.setAttribute("inert", "");
        document.body.classList.remove("page-open");
        openButton?.focus({ preventScroll: true });

        // Restore scrolling once the page has shrunk back.
        window.setTimeout(() => {
            if (!page.classList.contains("is-open")) {
                document.body.style.overflow = "";
            }
        }, 720);
    }

    openButton?.addEventListener("click", open);
    backButton?.addEventListener("click", close);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && page.classList.contains("is-open")) {
            close();
        }
    });
}

setupSlidePage({
    openId: "openColleaguesPage",
    pageId: "colleaguesDetailPage",
    backId: "backFromColleagues"
});

setupSlidePage({
    openId: "openGraphsPage",
    pageId: "graphsDetailPage",
    backId: "backFromGraphs"
});

/* -----------------------------------
   3D MODELS
   ----------------------------------- */

// Loads a model into a <model-viewer>, shows a loading indicator until it is
// ready, and falls back to an embedded copy when the .glb can't be fetched
// (browsers block that when a page is opened by double-click, file://).
function loadModel(viewer) {
    if (!viewer || viewer.dataset.started) return;
    viewer.dataset.started = "true";

    const container = viewer.parentElement;
    const loader = container.querySelector(".model-loading");
    const fill = loader?.querySelector(".model-loading-bar b");
    const glbName = viewer.dataset.src;
    let triedFallback = false;

    function finishLoading() {
        loader?.classList.add("is-done");
    }

    function showError() {
        finishLoading();
        if (container.querySelector(".model-error")) return;
        const message = document.createElement("p");
        message.className = "model-error";
        message.textContent = "This model could not be loaded.";
        container.appendChild(message);
    }

    function useEmbeddedModel() {
        triedFallback = true;
        const script = document.createElement("script");
        script.src = glbName.replace(/\.glb$/i, ".data.js");
        script.onload = () => {
            try {
                const binary = atob(window.MODEL_DATA[glbName]);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                viewer.src = URL.createObjectURL(
                    new Blob([bytes], { type: "model/gltf-binary" })
                );
                delete window.MODEL_DATA[glbName];
            } catch (error) {
                console.error("Could not decode embedded model:", error);
                showError();
            }
        };
        script.onerror = showError;
        document.head.appendChild(script);
    }

    viewer.addEventListener("progress", (event) => {
        const total = event.detail?.totalProgress ?? 0;
        fill?.style.setProperty("--load", String(total));
    });

    viewer.addEventListener("load", finishLoading);

    viewer.addEventListener("error", () => {
        if (!triedFallback) useEmbeddedModel();
        else showError();
    });

    viewer.src = glbName;
}

// Main astronaut: starts loading right away. Hovering over it fades the
// model to transparent (with a slight blur); moving away brings it back.
(function setupMainAstronaut() {
    const viewer = document.getElementById("astronautModel");
    if (!viewer) return;

    loadModel(viewer);

    const GHOST_ALPHA = 0.22;   // how transparent it gets (0 to 1)
    const FADE_MS = 500;        // fade duration

    let baseColors = [];        // original colour of each material
    let alphaModes = [];        // original alpha mode of each material
    let currentAlpha = 1;
    let targetAlpha = 1;
    let fadeFrame = 0;

    /* -----------------------------------
       BODY HEALTH COLOURS
       The astronaut is split into regions. Each region can be tinted
       by a 0-100 score: healthy parts stay uncoloured; unhealthy ones turn
       yellow, then orange, then red as the condition becomes critical.
       ----------------------------------- */

    const REGIONS = ["head", "torso", "pack", "armLeft", "armRight", "legLeft", "legRight"];

    // Names that can be passed in addition to the single regions.
    const REGION_GROUPS = {
        arms: ["armLeft", "armRight"],
        legs: ["legLeft", "legRight"]
    };

    // Score thresholds. At or above HEALTHY_FROM the part keeps its normal,
    // uncoloured look. Below it the colour moves yellow -> orange -> red.
    const HEALTHY_FROM = 75;
    const HEALTH_STOPS = [          // score, colour (sRGB)
        [60, [242, 207,  29]],      // yellow  - slightly off
        [40, [242, 140,  40]],      // orange  - concerning
        [20, [229,  72,  77]]       // red     - critical (this and below)
    ];

    const healthScores = {};        // region -> 0-100 (absent = no data)

    function srgbToLinear(channel) {
        const c = channel / 255;
        return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }

    // Returns a linear RGB tint, or null when the part is healthy (no colouring).
    // "base" is the part's normal colour; the tint fades in from it.
    function healthColor(score, base) {
        const value = Math.max(0, Math.min(100, score));
        if (value >= HEALTHY_FROM) return null;

        const toLinear = (c) => c.map(srgbToLinear);
        const mix = (from, to, t) => from.map((c, k) => c + (to[k] - c) * t);

        // Between "healthy" and the first (yellow) stop.
        const [firstScore, firstColor] = HEALTH_STOPS[0];
        if (value > firstScore) {
            const t = (HEALTHY_FROM - value) / (HEALTHY_FROM - firstScore);
            return mix(base.slice(0, 3), toLinear(firstColor), t);
        }

        // Between the coloured stops, then flat red at the bottom.
        for (let i = 1; i < HEALTH_STOPS.length; i++) {
            const [lo, cLo] = HEALTH_STOPS[i];
            const [hi, cHi] = HEALTH_STOPS[i - 1];
            if (value >= lo) {
                return mix(toLinear(cHi), toLinear(cLo), (hi - value) / (hi - lo));
            }
        }
        return toLinear(HEALTH_STOPS[HEALTH_STOPS.length - 1][1]);
    }

    function captureMaterials() {
        const materials = viewer.model?.materials || [];
        baseColors = materials.map((m) => [...m.pbrMetallicRoughness.baseColorFactor]);
        alphaModes = materials.map((m) => m.getAlphaMode());
    }

    // Paints every material: its health colour (if any) at the current opacity.
    function applyAlpha(alpha) {
        const materials = viewer.model?.materials || [];
        materials.forEach((material, i) => {
            const base = baseColors[i] || [1, 1, 1, 1];
            const region = material.name.replace(/^region_/, "");
            const score = healthScores[region];
            const tint = score === undefined ? null : healthColor(score, base);
            const rgb = tint || base;

            // Only use blending while actually transparent, so the solid
            // astronaut keeps its normal, artefact-free rendering.
            material.setAlphaMode(alpha < 0.999 ? "BLEND" : (alphaModes[i] || "OPAQUE"));
            material.pbrMetallicRoughness.setBaseColorFactor(
                [rgb[0], rgb[1], rgb[2], base[3] * alpha]
            );
        });
    }

    function refreshColors() {
        if (!viewer.loaded || !viewer.model) return;
        if (!baseColors.length) captureMaterials();
        applyAlpha(currentAlpha);
    }

    function updateLegend() {
        const legend = document.getElementById("bodyLegend");
        if (legend) legend.hidden = Object.keys(healthScores).length === 0;
    }

    // part: a region name, "arms" or "legs". score: 0-100, or null to clear.
    function setBodyPartHealth(part, score) {
        const targets = REGION_GROUPS[part] || (REGIONS.includes(part) ? [part] : []);
        const numeric = Number(score);

        targets.forEach((region) => {
            if (score === null || score === undefined || !Number.isFinite(numeric)) {
                delete healthScores[region];
            } else {
                healthScores[region] = Math.max(0, Math.min(100, numeric));
            }
        });

        refreshColors();
        updateLegend();
    }

    window.MedPointBody = { setBodyPartHealth, regions: REGIONS };

    function fadeTo(target) {
        if (!viewer.loaded || !viewer.model) return;
        if (!baseColors.length) captureMaterials();

        targetAlpha = target;
        viewer.classList.toggle("is-blurred", target < 1);

        cancelAnimationFrame(fadeFrame);
        const from = currentAlpha;
        const start = performance.now();

        function step(now) {
            const t = Math.min(1, (now - start) / FADE_MS);
            const eased = 1 - Math.pow(1 - t, 3);
            currentAlpha = from + (target - from) * eased;
            applyAlpha(currentAlpha);
            if (t < 1) fadeFrame = requestAnimationFrame(step);
        }

        fadeFrame = requestAnimationFrame(step);
    }

    viewer.addEventListener("load", () => {
        baseColors = [];
        currentAlpha = 1;
        targetAlpha = 1;
        viewer.classList.remove("is-blurred");
        refreshColors();    // apply any scores that arrived before the model
    });

    /* HIT BOX
       The fade only happens while the pointer is over the astronaut's body.
       The viewer asks the 3D scene what is under the pointer, so the hit box
       follows the model's real outline (empty space around him does nothing). */
    const CHECK_EVERY_MS = 60;

    let hovering = false;
    let lastPoint = null;
    let lastCheck = 0;
    let checkTimer = 0;

    function isOverModel(x, y) {
        if (!viewer.loaded || !viewer.model) return false;
        try {
            return Boolean(viewer.positionAndNormalFromPoint(x, y));
        } catch (error) {
            return false;
        }
    }

    function setHovering(over) {
        if (over === hovering) return;
        hovering = over;
        fadeTo(over ? GHOST_ALPHA : 1);
    }

    function checkPointer() {
        checkTimer = 0;
        lastCheck = performance.now();
        if (!lastPoint) return;
        setHovering(isOverModel(lastPoint.x, lastPoint.y));
    }

    viewer.addEventListener("pointermove", (event) => {
        if (event.pointerType === "touch") return;
        lastPoint = { x: event.clientX, y: event.clientY };
        if (checkTimer) return;
        const wait = Math.max(0, CHECK_EVERY_MS - (performance.now() - lastCheck));
        checkTimer = window.setTimeout(checkPointer, wait);
    });

    viewer.addEventListener("pointerleave", () => {
        lastPoint = null;
        window.clearTimeout(checkTimer);
        checkTimer = 0;
        setHovering(false);
    });

    // Touch has no hover: tapping the astronaut toggles the fade.
    viewer.addEventListener("click", (event) => {
        if (event.pointerType !== "touch") return;
        const over = isOverModel(event.clientX, event.clientY);
        hovering = over ? !hovering : false;
        fadeTo(hovering ? GHOST_ALPHA : 1);
    });
})();

// Crew models: loaded the first time the crew page is opened.
(function setupCrewModels() {
    const button = document.getElementById("openColleaguesPage");

    function loadCrew() {
        document.querySelectorAll(".crew-model").forEach(loadModel);
    }

    button?.addEventListener("click", loadCrew, { once: true });
})();

/* -----------------------------------
   HEALTH SUGGESTIONS
   ----------------------------------- */

const suggestionsList = document.getElementById("healthSuggestions");

function updateHealthSuggestions(suggestions) {
    if (!suggestionsList || !Array.isArray(suggestions)) return;

    const cleaned = suggestions
        .map((item) => {
            if (typeof item === "string") return item.trim();
            if (item && typeof item.text === "string") return item.text.trim();
            return "";
        })
        .filter(Boolean);

    suggestionsList.replaceChildren();

    if (cleaned.length === 0) {
        const emptyItem = document.createElement("li");
        emptyItem.className = "empty-item";
        emptyItem.textContent = "No health suggestions are available yet.";
        suggestionsList.appendChild(emptyItem);
        return;
    }

    cleaned.forEach((suggestion) => {
        const item = document.createElement("li");
        item.textContent = suggestion;
        suggestionsList.appendChild(item);
    });
}

/* -----------------------------------
   SUMMARY PROGRESS BARS
   ----------------------------------- */

function updateMetricProgress(elementId, value) {
    const bar = document.getElementById(elementId);
    const numericValue = Number(value);

    if (!bar || !Number.isFinite(numericValue)) return;

    const bounded = Math.max(0, Math.min(100, numericValue));

    bar.style.setProperty("--progress", `${bounded}%`);
    bar.dataset.value = String(bounded);
    bar.setAttribute("aria-valuenow", String(bounded));

    const label = bar.parentElement?.querySelector("strong");
    if (label) label.textContent = `${Math.round(bounded)}%`;

    // Keep the astronaut's colours in step with the summary bars.
    const BAR_TO_BODY = {
        progressSleep: "head",          // sleep      -> head
        progressBoneDensity: "legs",    // bone       -> legs
        progressVO2: "pack"             // VO2        -> oxygen pack
    };
    if (BAR_TO_BODY[elementId]) {
        window.MedPointBody?.setBodyPartHealth(BAR_TO_BODY[elementId], bounded);
    }
}

/* -----------------------------------
   HEART RATE AND SLEEP QUANTITY
   ----------------------------------- */

function setVital(elementId, text, unitText) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const unit = document.createElement("small");
    unit.textContent = unitText;
    element.replaceChildren(document.createTextNode(`${text} `), unit);
}

// Heart rate -> torso score: 100 inside the normal resting range (55-85 BPM),
// falling to 0 at 35 BPM or 130 BPM. Adjust to taste.
function heartRateScore(bpm) {
    if (bpm >= 55 && bpm <= 85) return 100;
    if (bpm < 55) return Math.max(0, ((bpm - 35) / 20) * 100);
    return Math.max(0, ((130 - bpm) / 45) * 100);
}

function updateVitals({ bpm, sleepHours } = {}) {
    if (bpm !== undefined && Number.isFinite(Number(bpm))) {
        setVital("bpmValue", Number(bpm), "BPM");
        window.MedPointBody?.setBodyPartHealth("torso", heartRateScore(Number(bpm)));
    }

    if (sleepHours !== undefined && Number.isFinite(Number(sleepHours))) {
        setVital("sleepValue", Number(sleepHours).toFixed(1), "hours");
    }
}

/* -----------------------------------
   GRAPH SUMMARY AND CHART
   ----------------------------------- */

function updateGraphSummary({ avgHr, recovery } = {}) {
    const hr = document.getElementById("avgHrValue");
    const rec = document.getElementById("recoveryValue");

    if (hr && Number.isFinite(Number(avgHr))) hr.textContent = `${Number(avgHr)} BPM`;
    if (rec && Number.isFinite(Number(recovery))) {
        rec.textContent = `${Math.round(Number(recovery))}%`;
        window.MedPointBody?.setBodyPartHealth("arms", Number(recovery));   // recovery -> arms
    }
}

const CHART_W = 420, CHART_H = 200, CHART_PAD = 20;
const GRID_LINES_Y = [25, 75, 125, 175];   // the horizontal grid lines drawn in the HTML

// Smooth line and filled-area paths for an array of numbers (any range), or null if fewer than 2.
// Optional `times` (ms, one per value) place the points by time instead of evenly.
// Also returns coords (points as 0-1 fractions of the viewBox), ticks (value at each grid line) and span.
function chartPaths(values, times) {
    const points = Array.isArray(values)
        ? values.map(Number).filter(Number.isFinite)
        : [];

    if (points.length < 2) return null;

    let min = Math.min(...points);
    let max = Math.max(...points);
    if (min === max) { min -= 1; max += 1; }   // flat series: draw it in the middle
    const span = max - min;

    const t0 = Array.isArray(times) ? times[0] : NaN;
    const tN = Array.isArray(times) ? times[times.length - 1] : NaN;
    const byTime = Array.isArray(times) && times.length === points.length
        && times.every(Number.isFinite) && tN > t0;

    const coords = points.map((v, i) => [
        (byTime ? (times[i] - t0) / (tN - t0) : i / (points.length - 1)) * CHART_W,
        CHART_H - CHART_PAD - ((v - min) / span) * (CHART_H - CHART_PAD * 2)
    ]);

    let d = `M ${coords[0][0]} ${coords[0][1]}`;
    for (let i = 1; i < coords.length; i++) {
        const [x0, y0] = coords[i - 1];
        const [x1, y1] = coords[i];
        const cx = (x0 + x1) / 2;
        d += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
    }

    return {
        line: d,
        area: `${d} L ${CHART_W} ${CHART_H} L 0 ${CHART_H} Z`,
        coords: coords.map(([x, y]) => [x / CHART_W, y / CHART_H]),
        ticks: GRID_LINES_Y.map(y => ({
            y: y / CHART_H,
            value: min + ((CHART_H - CHART_PAD - y) / (CHART_H - CHART_PAD * 2)) * span
        })),
        span
    };
}

// Draws a smooth line from an array of numbers (any range).
function updateChart(values) {
    const line = document.getElementById("chartLinePath");
    const area = document.getElementById("chartArea");
    const empty = document.getElementById("chartEmpty");

    if (!line || !area) return;

    const paths = chartPaths(values);
    line.setAttribute("d", paths ? paths.line : "");
    area.setAttribute("d", paths ? paths.area : "");
    if (empty) empty.hidden = Boolean(paths);
}

/* -----------------------------------
   HEALTH DATA IN TIME (history)
   ----------------------------------- */

// window.MED_POINT_HISTORY comes from health_history.js, written by export_history.py
// (per astronaut and metric: label, unit, points [time, value], summary).
// The first astronaut in the file is shown.

const SVG_NS = "http://www.w3.org/2000/svg";

const MAX_DOTS = 40;           // above this many readings only the latest dot is drawn
const SHORT_HISTORY_MS = 2 * 24 * 60 * 60 * 1000;

function formatValue(value) {
    return String(Number(value.toFixed(2)));
}

function parseTime(timestamp) {
    return new Date(timestamp.replace(" ", "T")).getTime();
}

// "5 Nov", or "5 Nov, 14:30" when withTime is set.
function formatDate(ms, withTime) {
    const date = new Date(ms);
    if (Number.isNaN(date.getTime())) return "";
    const day = date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
    return withTime
        ? `${day}, ${date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
        : day;
}

function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

// A chart label or dot placed inside the frame by --x / --y (fractions of its size).
function makePlotItem(tag, className, x, y, text) {
    const item = makeElement(tag, className, text);
    if (x !== null) item.style.setProperty("--x", x);
    item.style.setProperty("--y", y);
    return item;
}

function makeStatTile(label, value) {
    const tile = makeElement("div");
    tile.append(makeElement("span", "", label), makeElement("strong", "", value));
    return tile;
}

function formatChange(change) {
    if (change > 0) return `▲ +${formatValue(change)}`;
    if (change < 0) return `▼ ${formatValue(change)}`;
    return "0";
}

const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_RANGE = "All";

// Start of each time range, counted back from `end` (ms). null means no limit.
const RANGE_STARTS = {
    "1D": end => end - DAY_MS,
    "5D": end => end - 5 * DAY_MS,
    "1M": end => shiftDate(end, "setMonth", "getMonth", -1),
    "3M": end => shiftDate(end, "setMonth", "getMonth", -3),
    "YTD": end => new Date(new Date(end).getFullYear(), 0, 1).getTime(),
    "1Y": end => shiftDate(end, "setFullYear", "getFullYear", -1),
    "5Y": end => shiftDate(end, "setFullYear", "getFullYear", -5),
    "All": () => null
};

function shiftDate(ms, setter, getter, amount) {
    const date = new Date(ms);
    date[setter](date[getter]() + amount);
    return date.getTime();
}

// Points at or after `start` (ms); null keeps them all.
function pointsInRange(points, start) {
    return start === null ? points : points.filter(([time]) => parseTime(time) >= start);
}

// Latest reading time over all metrics of an astronaut (not the clock, so demo data works).
function latestReading(astronaut) {
    const times = Object.values(astronaut.metrics)
        .flatMap(metric => metric.points.map(([time]) => parseTime(time)));
    return times.length ? Math.max(...times) : null;
}

function emptyMessage(count) {
    return count === 0 ? "No readings in this range" : "Not enough readings in this range";
}

function drawLine(svg, paths) {
    svg.querySelectorAll("path").forEach(path => path.remove());
    if (!paths) return;
    [["chart-area", paths.area], ["chart-line", paths.line]].forEach(([name, d]) => {
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("class", name);
        path.setAttribute("d", d);
        svg.appendChild(path);
    });
}

function drawAxesAndDots(frame, paths, times, values, metric) {
    frame.classList.add("has-axes");
    const decimals = paths.span >= 20 ? 0 : paths.span >= 2 ? 1 : 2;
    paths.ticks.forEach(({ y, value }) =>
        frame.append(makePlotItem("span", "chart-y-tick", null, y, value.toFixed(decimals))));

    const lastIndex = paths.coords.length - 1;
    paths.coords.forEach(([x, y], i) => {
        const isLatest = i === lastIndex;
        if (paths.coords.length > MAX_DOTS && !isLatest) return;
        const dot = makePlotItem("span", isLatest ? "chart-dot latest" : "chart-dot", x, y);
        dot.title = `${formatDate(times[i], true)}: ${formatValue(values[i])} ${metric.unit}`;
        frame.append(dot);
    });
}

function makeStatsRow(values) {
    const stats = makeElement("div", "graph-card-stats");
    stats.append(
        makeStatTile("Min", formatValue(Math.min(...values))),
        makeStatTile("Avg", formatValue(values.reduce((sum, v) => sum + v, 0) / values.length)),
        makeStatTile("Max", formatValue(Math.max(...values))),
        makeStatTile("Change", formatChange(values[values.length - 1] - values[0]))
    );
    return stats;
}

// Fills one card from metric.points (any number of them, including none).
function fillGraphCard(card, metric) {
    const values = metric.points.map(([, value]) => value);
    const times = metric.points.map(([time]) => parseTime(time));
    const first = times[0];
    const last = times[times.length - 1];
    const date = ms => formatDate(ms, last - first < SHORT_HISTORY_MS);
    const svg = card.querySelector(".health-chart");
    const empty = card.querySelector(".chart-empty");
    const frame = card.querySelector(".chart-frame");
    const paths = chartPaths(values, times);

    card.querySelector(".graph-card-header strong").textContent = values.length
        ? `${formatValue(values[values.length - 1])} ${metric.unit}`
        : "—";

    drawLine(svg, paths);
    if (empty) {
        empty.hidden = Boolean(paths);
        if (!paths) empty.textContent = emptyMessage(values.length);
    }
    svg.setAttribute("aria-label", values.length
        ? `${metric.label} over time, ${date(first)} to ${date(last)}.`
        : `${metric.label} over time, no readings in this range.`);

    // Rebuilt on every fill, so remove what an earlier fill (or a cloned card) added.
    card.querySelectorAll(".graph-card-sub, .chart-x-axis, .graph-card-stats, .chart-y-tick, .chart-dot")
        .forEach(element => element.remove());

    const span = values.length ? ` · ${date(first)} – ${date(last)}` : "";
    frame.before(makeElement("p", "graph-card-sub", `${values.length} readings${span} · ${metric.unit}`));
    if (!values.length) return;

    if (paths) drawAxesAndDots(frame, paths, times, values, metric);

    const axis = makeElement("div", "chart-x-axis");
    const axisTimes = paths ? [first, (first + last) / 2, last] : [first];
    axis.append(...axisTimes.map(ms => makeElement("span", "", date(ms))));
    frame.after(axis);
    card.appendChild(makeStatsRow(values));
}

// One button per range; clicking one calls onSelect(key).
function makeRangeSelector(onSelect) {
    const selector = makeElement("div", "range-selector");
    selector.setAttribute("role", "group");
    selector.setAttribute("aria-label", "Time range");
    const buttons = Object.keys(RANGE_STARTS).map(key => {
        const button = makeElement("button", "range-button", key);
        button.type = "button";
        button.addEventListener("click", () => onSelect(key));
        return [key, button];
    });
    selector.append(...buttons.map(([, button]) => button));
    selector.select = active => buttons.forEach(([key, button]) => {
        button.setAttribute("aria-pressed", String(key === active));
        button.classList.toggle("is-active", key === active);
    });
    return selector;
}

function loadHealthHistory() {
    const astronauts = window.MED_POINT_HISTORY?.astronauts ?? [];
    const wanted = new URLSearchParams(window.location.search).get("astronaut_id");
    const astronaut = wanted === null ? astronauts[0] : astronauts.find(a => a.id === Number(wanted));
    const grid = document.querySelector(".graph-detail-grid");
    if (!astronaut || !grid) return;

    const spare = grid.querySelector(".graph-card").cloneNode(true);   // layout for extra metrics
    const shown = new Set();
    grid.querySelectorAll(".graph-card[data-metric]").forEach(card => shown.add(card.dataset.metric));

    Object.entries(astronaut.metrics)
        .filter(([key]) => !shown.has(key))
        .forEach(([key, metric]) => {
            const card = spare.cloneNode(true);
            card.dataset.metric = key;
            card.querySelector(".crew-member-label").textContent = metric.label;
            grid.appendChild(card);
        });

    const end = latestReading(astronaut);
    const selector = makeRangeSelector(showRange);
    function showRange(key) {
        const start = end === null ? null : RANGE_STARTS[key](end);
        grid.querySelectorAll(".graph-card[data-metric]").forEach(card => {
            const metric = astronaut.metrics[card.dataset.metric];
            if (metric) fillGraphCard(card, { ...metric, points: pointsInRange(metric.points, start) });
        });
        selector.select(key);
    }
    grid.before(selector);
    showRange(DEFAULT_RANGE);
}

/* -----------------------------------
   HEALTH SUGGESTIONS API
   ----------------------------------- */

// Set this to your backend endpoint when ready. It should return JSON.
const SUGGESTIONS_API_URL = ""; // e.g. "/api/health-suggestions"

async function loadHealthSuggestions() {
    if (!SUGGESTIONS_API_URL) {
        updateHealthSuggestions([]);
        return;
    }

    try {
        const response = await fetch(SUGGESTIONS_API_URL, {
            headers: { "Accept": "application/json" }
        });

        if (!response.ok) {
            throw new Error(`Suggestions request failed: ${response.status}`);
        }

        const data = await response.json();
        updateHealthSuggestions(Array.isArray(data) ? data : data.suggestions);
    } catch (error) {
        console.error("Could not load health suggestions:", error);
        updateHealthSuggestions([]);
    }
}

/* -----------------------------------
   PUBLIC DASHBOARD FUNCTIONS
   ----------------------------------- */

// Colour body parts directly, e.g.
// updateBodyHealth({ head: 82, torso: 64, pack: 40, arms: 90, legs: 55 })
// Use null to clear a part. Also accepts armLeft, armRight, legLeft, legRight.
function updateBodyHealth(scores = {}) {
    Object.entries(scores).forEach(([part, score]) => {
        window.MedPointBody?.setBodyPartHealth(part, score);
    });
}

window.MedPointDashboard = {
    updateBodyHealth,
    updateHealthSuggestions,
    updateMetricProgress,
    updateVitals,
    updateGraphSummary,
    updateChart
};

loadHealthSuggestions();
loadHealthHistory();
