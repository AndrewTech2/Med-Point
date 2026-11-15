/* -----------------------------------
   Med-Point | graph category filter
   Builds the category buttons beside the health graphs and shows only the
   cards of the chosen category. Grouping comes from metric_categories.js.
   Cards without a data-metric count as "other" and show only under All.
   ----------------------------------- */

(function setupGraphFilters() {
    const ALL = "all";
    const OTHER = "other";
    const CATEGORIES = window.MED_POINT_CATEGORIES;
    const categories = window.MedPointCategories;
    const nav = document.getElementById("categoryFilter");
    const grid = document.getElementById("graphDetailGrid");
    if (!nav || !grid || !CATEGORIES || !categories) return;

    const liveRegion = createLiveRegion();
    const KEY_STEP = Object.freeze({ ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 });
    let current = ALL;
    let lastSignature = null;

    function createLiveRegion() {
        const region = document.createElement("div");
        region.className = "visually-hidden";
        region.setAttribute("aria-live", "polite");
        document.body.appendChild(region);
        return region;
    }

    function cardCategory(card) {
        return (card.dataset.metric && categories.categoryOf(card.dataset.metric)) || OTHER;
    }

    // Card counts keyed by category, plus the total under ALL.
    function countCards() {
        const counts = { [ALL]: 0 };
        grid.querySelectorAll(".graph-card").forEach(card => {
            const key = cardCategory(card);
            counts[ALL] += 1;
            counts[key] = (counts[key] || 0) + 1;
        });
        return counts;
    }

    function isSelectable(key, counts) {
        if (key === ALL) return counts[ALL] > 0;
        const isKnown = CATEGORIES.some(category => category.key === key);
        return isKnown && (counts[key] || 0) > 0;
    }

    function makeButton(key, count) {
        const label = key === ALL ? "All" : categories.labelOf(key);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "category-button";
        button.dataset.category = key;
        button.setAttribute("aria-label", `${label}, ${count} ${count === 1 ? "graph" : "graphs"}`);

        const name = document.createElement("span");
        name.textContent = label;
        const badge = document.createElement("span");
        badge.className = "category-count";
        badge.setAttribute("aria-hidden", "true");
        badge.textContent = String(count);

        button.append(name, badge);
        button.addEventListener("click", () => select(key));
        return button;
    }

    function buildButtons(counts) {
        const keys = [ALL, ...CATEGORIES.map(category => category.key).filter(key => counts[key] > 0)];
        nav.replaceChildren(...keys.map(key => makeButton(key, counts[key])));
    }

    function applyFilter() {
        grid.querySelectorAll(".graph-card").forEach(card => {
            card.hidden = !(current === ALL || cardCategory(card) === current);
        });
    }

    function syncButtons() {
        nav.querySelectorAll(".category-button").forEach(button => {
            const isActive = button.dataset.category === current;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
    }

    function announce(key, count) {
        const name = key === ALL ? "all" : categories.labelOf(key);
        liveRegion.textContent = `Showing ${name} graphs (${count})`;
    }

    function select(categoryKey) {
        const counts = countCards();
        if (!isSelectable(categoryKey, counts)) return false;
        current = categoryKey;
        applyFilter();
        syncButtons();
        announce(categoryKey, counts[categoryKey]);
        return true;
    }

    // Rebuilds the buttons only when the card counts change, so focus is kept
    // across unrelated DOM mutations.
    function refresh() {
        const counts = countCards();
        if (!isSelectable(current, counts)) current = ALL;
        const signature = JSON.stringify(counts);
        if (signature !== lastSignature) {
            lastSignature = signature;
            buildButtons(counts);
        }
        applyFilter();
        syncButtons();
    }

    function focusStep(event) {
        const buttons = Array.from(nav.querySelectorAll(".category-button"));
        const index = buttons.indexOf(event.target);
        if (index === -1) return null;
        if (event.key in KEY_STEP) {
            return buttons[(index + KEY_STEP[event.key] + buttons.length) % buttons.length];
        }
        if (event.key === "Home") return buttons[0];
        if (event.key === "End") return buttons[buttons.length - 1];
        return null;
    }

    function onNavKeyDown(event) {
        const target = focusStep(event);
        if (!target) return;
        event.preventDefault();
        target.focus();
    }

    nav.addEventListener("keydown", onNavKeyDown);
    document.addEventListener("medpoint:select-category", event => {
        select(event.detail && event.detail.category);
    });
    new MutationObserver(refresh).observe(grid, { childList: true });
    refresh();

    window.MedPointFilters = Object.freeze({
        select,
        current: () => current
    });
})();
