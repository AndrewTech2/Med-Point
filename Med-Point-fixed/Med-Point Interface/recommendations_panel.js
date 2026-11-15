/* -----------------------------------
   Med-Point | recommendations panel
   Renders the selected astronaut's recommendations into #healthSuggestions.
   Data: GET /api/astronauts/<id>/recommendations on http(s), with the embedded
   copy in window.MED_POINT_HISTORY as the fallback (and the only source on file://).
   All markup is built with createElement + textContent; nothing is parsed as HTML.
   ----------------------------------- */

(function recommendationsPanel() {
    "use strict";

    const TARGET_ID = "healthSuggestions";
    const GRAPHS_BUTTON_ID = "openGraphsPage";
    const SELECT_EVENT = "medpoint:select-category";
    const API_TIMEOUT_MS = 5000;
    const PREVIEW_COUNT = 5;
    const SELECT_DELAY_MS = 50;
    const MIN_LEVEL = -1;
    const MAX_LEVEL = 3;
    const REGION_KEYS = Object.freeze(["head", "torso", "arms", "legs"]);
    const STATUS_LEVELS = Object.freeze({ UNKNOWN: -1, OK: 0, WATCH: 1, ACTION: 2, URGENT: 3 });
    const MONTHS = Object.freeze(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]);
    const RECORDED_AT_PATTERN = /^\d{4}-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/;
    const ASTRONAUT_ID_PATTERN = /^\d+$/;

    const TEXT = Object.freeze({
        loading: "Loading recommendations…",
        empty: "No recommendations available yet.",
        inRange: "All evaluated measurements are within range.",
        multiSystem: "Multi-system review",
        showMore: (count) => `Show ${count} more`,
        showFewer: "Show fewer"
    });

    let latestRequest = 0;
    let currentPayload = null;
    let isExpanded = false;
    let hasLoaded = false;
    let slots = null;

    /* ---------- DOM helpers ---------- */

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    /* ---------- normalisation (pure) ---------- */

    function isPlainObject(value) {
        return value !== null && typeof value === "object" && !Array.isArray(value);
    }

    function asArray(value) {
        return Array.isArray(value) ? value : [];
    }

    function cleanString(value) {
        return typeof value === "string" ? value.trim() : "";
    }

    function stringList(value) {
        return asArray(value).map(cleanString).filter(Boolean);
    }

    function normalizeStatus(value) {
        const status = cleanString(value).toUpperCase();
        return Object.prototype.hasOwnProperty.call(STATUS_LEVELS, status) ? status : "UNKNOWN";
    }

    // A non-finite level falls back to the status default; the result is clamped to -1..3.
    function normalizeLevel(value, status) {
        const level = Number.isFinite(value) ? value : STATUS_LEVELS[status];
        return Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, level));
    }

    function firstVariable(rules) {
        const found = asArray(rules)
            .filter(isPlainObject)
            .find(rule => cleanString(rule.variable));
        return found ? cleanString(found.variable) : "";
    }

    function normalizeRecommendation(raw) {
        if (!isPlainObject(raw)) return null;
        const action = cleanString(raw.action);
        if (!action) return null;
        const status = normalizeStatus(raw.status);
        return {
            action,
            status,
            level: normalizeLevel(raw.level, status),
            ruleIds: stringList(raw.rule_ids),
            variable: firstVariable(raw.rules),
            systems: stringList(raw.systems),
            metrics: stringList(raw.metrics)
        };
    }

    function normalizeMeasureThis(value) {
        return asArray(value)
            .filter(isPlainObject)
            .map(item => ({
                key: cleanString(item.key),
                label: cleanString(item.label) || cleanString(item.key)
            }))
            .filter(item => item.key);
    }

    // Keeps only the body regions whose values are finite numbers.
    function normalizeRegions(value) {
        if (!isPlainObject(value)) return {};
        return Object.fromEntries(
            REGION_KEYS
                .filter(key => Number.isFinite(value[key]))
                .map(key => [key, value[key]])
        );
    }

    function normalizePayload(raw) {
        if (!isPlainObject(raw) || !Array.isArray(raw.recommendations)) return null;
        return Object.freeze({
            name: cleanString(raw.name),
            recordedAt: cleanString(raw.recorded_at),
            overall: normalizeStatus(raw.overall),
            multiSystemReview: raw.multi_system_review === true,
            recommendations: raw.recommendations.map(normalizeRecommendation).filter(Boolean),
            regions: normalizeRegions(raw.regions),
            measureThis: normalizeMeasureThis(raw.measure_this),
            disclaimer: cleanString(raw.disclaimer)
        });
    }

    // Stable sort by level, highest first; ties keep the engine order. Does not mutate input.
    function sortRecommendations(list) {
        return list
            .map((item, index) => ({ item, index }))
            .sort((a, b) => (b.item.level - a.item.level) || (a.index - b.index))
            .map(entry => entry.item);
    }

    // "2026-11-14 18:00:00" -> "14 Nov, 18:00". Unrecognised input is returned unchanged.
    function formatRecordedAt(value) {
        const text = cleanString(value);
        const match = RECORDED_AT_PATTERN.exec(text);
        if (!match) return text;
        const monthName = MONTHS[Number(match[1]) - 1];
        if (!monthName) return text;
        return `${Number(match[2])} ${monthName}, ${match[3]}:${match[4]}`;
    }

    function categoryFor(rec) {
        const categories = window.MedPointCategories;
        if (!categories) return null;
        for (const metric of rec.metrics) {
            const key = categories.categoryOf(metric);
            if (key) return { key, label: categories.labelOf(key) || key };
        }
        return null;
    }

    /* ---------- astronaut and data loading ---------- */

    function validAstronautId(value) {
        return Number.isSafeInteger(value) && value > 0 ? value : null;
    }

    function historyAstronauts() {
        return asArray(window.MED_POINT_HISTORY?.astronauts).filter(isPlainObject);
    }

    // Same fallback as Script MIP.js: an id that is not in the history falls back to the first astronaut.
    function resolveAstronautId() {
        const requested = new URLSearchParams(location.search).get("astronaut_id");
        const requestedId = requested !== null && ASTRONAUT_ID_PATTERN.test(requested) ? validAstronautId(Number(requested)) : null;
        const astronauts = historyAstronauts();
        if (requestedId !== null && astronauts.some(item => item.id === requestedId)) return requestedId;
        const first = astronauts[0];
        return first && Number.isSafeInteger(first.id) ? first.id : null;
    }

    function embeddedPayload(astronautId) {
        const match = historyAstronauts().find(item => item.id === astronautId);
        return match ? normalizePayload(match.recommendations) : null;
    }

    function isHttpPage() {
        return location.protocol === "http:" || location.protocol === "https:";
    }

    async function fetchJson(url) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
        try {
            const response = await fetch(url, {
                headers: { Accept: "application/json" },
                signal: controller.signal
            });
            if (!response.ok) throw new Error(`Recommendations request failed: ${response.status}`);
            return await response.json();
        } finally {
            clearTimeout(timer);
        }
    }

    async function loadPayload(astronautId) {
        if (!isHttpPage()) return embeddedPayload(astronautId);
        try {
            const payload = normalizePayload(await fetchJson(`/api/astronauts/${astronautId}/recommendations`));
            if (!payload) throw new Error("Recommendations response has an unexpected shape");
            return payload;
        } catch (error) {
            console.warn("Could not load recommendations, using the embedded copy:", error);
            return embeddedPayload(astronautId);
        }
    }

    /* ---------- rendering ---------- */

    // Creates the once-per-panel elements around the list: overall line before, note and disclaimer after.
    function ensureSlots(list) {
        if (slots && slots.list === list && list.isConnected) return slots;
        const overall = el("p", "rec-overall");
        const note = el("p", "rec-note");
        const disclaimer = el("p", "rec-disclaimer");
        overall.hidden = true;
        note.hidden = true;
        disclaimer.hidden = true;
        list.before(overall);
        list.after(note);
        note.after(disclaimer);
        slots = { list, overall, note, disclaimer };
        return slots;
    }

    function hideSlots() {
        if (!slots) return;
        [slots.overall, slots.note, slots.disclaimer].forEach(slot => {
            slot.textContent = "";
            slot.hidden = true;
        });
    }

    function renderOverall(target, payload) {
        const details = [
            payload.name,
            payload.recordedAt ? `latest ${formatRecordedAt(payload.recordedAt)}` : ""
        ].filter(Boolean);
        target.className = `rec-overall rec-${payload.overall.toLowerCase()}`;
        target.replaceChildren(el("span", "rec-badge", payload.overall));
        if (details.length) target.appendChild(el("span", "rec-overall-text", ` · ${details.join(" · ")}`));
        if (payload.multiSystemReview) target.appendChild(el("span", "rec-multi", TEXT.multiSystem));
        target.hidden = false;
    }

    function renderNote(target, payload) {
        const count = payload.measureThis.length;
        target.textContent = count ? `${count} ${count === 1 ? "input" : "inputs"} not measured` : "";
        target.hidden = count === 0;
    }

    function renderDisclaimer(target, payload) {
        target.textContent = payload.disclaimer;
        target.hidden = !payload.disclaimer;
    }

    function buildMeta(rec) {
        const meta = el("span", "rec-meta");
        const pieces = [
            rec.ruleIds.length ? el("span", "rec-rule-ids", rec.ruleIds.join(", ")) : null,
            rec.variable ? el("span", "", rec.variable) : null,
            rec.systems.length ? el("span", "", rec.systems.join(", ")) : null
        ].filter(Boolean);
        pieces.forEach((piece, index) => {
            if (index > 0) {
                const separator = el("span", "rec-sep", "·");
                separator.setAttribute("aria-hidden", "true");
                meta.appendChild(separator);
            }
            meta.appendChild(piece);
        });
        return meta;
    }

    function selectCategory(categoryKey) {
        document.getElementById(GRAPHS_BUTTON_ID)?.click();
        setTimeout(() => {
            document.dispatchEvent(new CustomEvent(SELECT_EVENT, { detail: { category: categoryKey } }));
        }, SELECT_DELAY_MS);
    }

    function buildLinkButton(rec, category) {
        const button = el("button", "rec-link");
        button.setAttribute("type", "button");
        button.setAttribute("aria-label", `${rec.status}: ${rec.action}. Show ${category.label} graphs.`);
        button.addEventListener("click", () => selectCategory(category.key));
        return button;
    }

    function buildItem(rec) {
        const category = categoryFor(rec);
        const item = el("li", `rec-item rec-${rec.status.toLowerCase()}`);
        const body = category ? buildLinkButton(rec, category) : el("div", "rec-body");
        body.replaceChildren(
            el("span", "rec-badge", rec.status),
            el("span", "rec-text", rec.action),
            buildMeta(rec)
        );
        item.appendChild(body);
        return item;
    }

    function buildToggle(hiddenCount) {
        const item = el("li", "rec-more");
        const button = el("button", "rec-more-button", isExpanded ? TEXT.showFewer : TEXT.showMore(hiddenCount));
        button.setAttribute("type", "button");
        button.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        button.addEventListener("click", toggleExpanded);
        item.appendChild(button);
        return item;
    }

    function toggleExpanded() {
        isExpanded = !isExpanded;
        if (currentPayload) renderList(slots.list, currentPayload);
    }

    function emptyMessage(payload) {
        return payload.overall === "OK" ? TEXT.inRange : TEXT.empty;
    }

    function renderList(list, payload) {
        const sorted = sortRecommendations(payload.recommendations);
        const visible = isExpanded ? sorted : sorted.slice(0, PREVIEW_COUNT);
        const nodes = visible.map(buildItem);
        if (sorted.length > PREVIEW_COUNT) nodes.push(buildToggle(sorted.length - PREVIEW_COUNT));
        if (sorted.length === 0) nodes.push(el("li", "empty-item", emptyMessage(payload)));
        list.replaceChildren(...nodes);
    }

    // Sends all four regions every time so a colour from the previous astronaut is cleared (null).
    function updateBody(regions) {
        const scores = Object.fromEntries(REGION_KEYS.map(key => [key, regions[key] ?? null]));
        window.MedPointDashboard?.updateBodyHealth?.(scores);
    }

    function renderEmpty(list) {
        list.removeAttribute("aria-busy");
        hideSlots();
        list.replaceChildren(el("li", "empty-item", TEXT.empty));
        updateBody({});
    }

    function renderPayload(list, payload) {
        const view = ensureSlots(list);
        renderList(list, payload);
        renderOverall(view.overall, payload);
        renderNote(view.note, payload);
        renderDisclaimer(view.disclaimer, payload);
        updateBody(payload.regions);
    }

    /* ---------- entry point ---------- */

    // Without a valid id (first load, or a bad request) the id comes from the URL.
    // On a switch the old rows stay until the new payload is ready, so there is no flash.
    async function reload(requestedId) {
        const list = document.getElementById(TARGET_ID);
        if (!list) return;
        const request = ++latestRequest;
        const astronautId = validAstronautId(requestedId) ?? resolveAstronautId();
        currentPayload = null;
        isExpanded = false;
        if (astronautId === null) {
            renderEmpty(list);
            hasLoaded = true;
            return;
        }
        if (hasLoaded) {
            list.setAttribute("aria-busy", "true");
        } else {
            hideSlots();
            list.replaceChildren(el("li", "loading-item", TEXT.loading));
        }
        const payload = await loadPayload(astronautId);
        if (request !== latestRequest) return;
        hasLoaded = true;
        if (!payload) {
            renderEmpty(list);
            return;
        }
        list.removeAttribute("aria-busy");
        currentPayload = payload;
        renderPayload(list, payload);
    }

    document.addEventListener("medpoint:astronaut-changed", event => {
        const astronautId = validAstronautId(event.detail?.astronautId);
        if (astronautId !== null) reload(astronautId);
    });

    window.MedPointRecommendations = Object.freeze({
        reload,
        _internal: Object.freeze({
            normalizePayload,
            normalizeRecommendation,
            normalizeStatus,
            normalizeLevel,
            sortRecommendations,
            formatRecordedAt,
            categoryFor,
            resolveAstronautId,
            embeddedPayload
        })
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => { reload(); }, { once: true });
    } else {
        reload();
    }
})();
