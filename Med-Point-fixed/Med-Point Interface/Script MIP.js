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
    let currentAlpha = 1;
    let targetAlpha = 1;
    let fadeFrame = 0;

    function captureMaterials() {
        const materials = viewer.model?.materials || [];
        baseColors = materials.map((m) => [...m.pbrMetallicRoughness.baseColorFactor]);
    }

    function applyAlpha(alpha) {
        const materials = viewer.model?.materials || [];
        materials.forEach((material, i) => {
            const base = baseColors[i] || [1, 1, 1, 1];
            material.setAlphaMode("BLEND");
            material.pbrMetallicRoughness.setBaseColorFactor(
                [base[0], base[1], base[2], base[3] * alpha]
            );
        });
    }

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

function updateVitals({ bpm, sleepHours } = {}) {
    if (bpm !== undefined && Number.isFinite(Number(bpm))) {
        setVital("bpmValue", Number(bpm), "BPM");
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
    if (rec && Number.isFinite(Number(recovery))) rec.textContent = `${Math.round(Number(recovery))}%`;
}

// Draws a smooth line from an array of numbers (any range).
function updateChart(values) {
    const line = document.getElementById("chartLinePath");
    const area = document.getElementById("chartArea");
    const empty = document.getElementById("chartEmpty");

    const points = Array.isArray(values)
        ? values.map(Number).filter(Number.isFinite)
        : [];

    if (!line || !area) return;

    if (points.length < 2) {
        line.setAttribute("d", "");
        area.setAttribute("d", "");
        if (empty) empty.hidden = false;
        return;
    }

    const W = 420, H = 200, pad = 20;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const span = max - min || 1;

    const coords = points.map((v, i) => [
        (i / (points.length - 1)) * W,
        H - pad - ((v - min) / span) * (H - pad * 2)
    ]);

    let d = `M ${coords[0][0]} ${coords[0][1]}`;
    for (let i = 1; i < coords.length; i++) {
        const [x0, y0] = coords[i - 1];
        const [x1, y1] = coords[i];
        const cx = (x0 + x1) / 2;
        d += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
    }

    line.setAttribute("d", d);
    area.setAttribute("d", `${d} L ${W} ${H} L 0 ${H} Z`);
    if (empty) empty.hidden = true;
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

window.MedPointDashboard = {
    updateHealthSuggestions,
    updateMetricProgress,
    updateVitals,
    updateGraphSummary,
    updateChart
};

loadHealthSuggestions();