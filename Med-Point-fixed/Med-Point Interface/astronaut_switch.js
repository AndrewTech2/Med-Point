/* -----------------------------------
   Med-Point | astronaut switching
   Crew cards pick the astronaut shown on the dashboard. A switch updates the
   URL (?astronaut_id=N) and dispatches medpoint:astronaut-changed, which the
   other scripts listen for. Listeners are attached once, at startup.
   ----------------------------------- */

(function astronautSwitch() {
    "use strict";

    const EVENT = "medpoint:astronaut-changed";
    const CREW_PAGE_ID = "colleaguesDetailPage";
    const BACK_BUTTON_ID = "backFromColleagues";
    const SWITCH_CLASS = "is-switching";

    const cards = Array.from(document.querySelectorAll("a.crew-card"));
    let current = null;

    // A positive safe integer, or null (for dataset strings, query values and ids).
    function toId(value) {
        const text = String(value ?? "");
        const id = /^\d+$/.test(text) ? Number(text) : NaN;
        return Number.isSafeInteger(id) && id > 0 ? id : null;
    }

    function historyAstronauts() {
        return window.MED_POINT_HISTORY?.astronauts ?? [];
    }

    function inHistory(id) {
        return historyAstronauts().some(a => a.id === id);
    }

    // Same rule as Script MIP.js: ?astronaut_id= when in the history, else the first astronaut.
    function initialId() {
        const requested = toId(new URLSearchParams(window.location.search).get("astronaut_id"));
        const hasCrewCard = requested !== null && cards.some(card => cardId(card) === requested);
        if (requested !== null && (inHistory(requested) || hasCrewCard)) return requested;
        return historyAstronauts()[0]?.id ?? null;
    }

    function cardId(card) {
        return toId(card.dataset.astronautId);
    }

    // Static mode leaves the Jinja placeholders in place: fill them from the export by card index.
    function prepareCard(card, index) {
        const historic = historyAstronauts()[index];
        // Only unrendered placeholders ("{{") are filled; a server-rendered empty card stays disabled.
        const unrendered = String(card.dataset.astronautId ?? "").includes("{{");
        if (unrendered && historic) {
            card.dataset.astronautId = String(historic.id);
            card.dataset.astronautName = historic.name;
            card.setAttribute("href", `?astronaut_id=${historic.id}`);
            const name = card.querySelector("strong");
            if (name) name.textContent = historic.name;
            const label = card.querySelector(".crew-username");
            if (label) label.textContent = historic.name;
        }
        if (cardId(card) === null) {
            card.removeAttribute("href");
            card.setAttribute("aria-disabled", "true");
        }
    }

    function markCurrent() {
        cards.forEach(card => {
            const isCurrent = current !== null && cardId(card) === current;
            card.classList.toggle("is-current", isCurrent);
            if (isCurrent) card.setAttribute("aria-current", "true");
            else card.removeAttribute("aria-current");
        });
    }

    function replaceUrlState(id) {
        try {
            history.replaceState({ astronautId: id }, "");
        } catch (error) {
            console.warn("Could not record the current astronaut in the history:", error);
        }
    }

    function pushUrl(id) {
        try {
            const url = new URL(location.href);
            url.searchParams.set("astronaut_id", String(id));
            history.pushState({ astronautId: id }, "", url);
        } catch (error) {
            // file:// pages cannot change the address; the switch still happens.
            console.warn("Could not update the address bar:", error);
        }
    }

    function restartSwitchAnimation() {
        const dashboard = document.querySelector("main.dashboard");
        if (!dashboard) return;
        dashboard.classList.remove(SWITCH_CLASS);
        void dashboard.offsetWidth;
        dashboard.classList.add(SWITCH_CLASS);
    }

    function closeCrewPage() {
        if (document.getElementById(CREW_PAGE_ID)?.classList.contains("is-open")) {
            document.getElementById(BACK_BUTTON_ID)?.click();
        }
    }

    function announce(id) {
        const card = cards.find(c => cardId(c) === id);
        const name = card?.querySelector("strong")?.textContent.trim()
            || historyAstronauts().find(a => a.id === id)?.name;
        const announcer = document.getElementById("astronautAnnouncer");
        if (announcer) announcer.textContent = `Showing ${name}'s dashboard`;
    }

    // Outside http(s) the page cannot ask the server, so an id missing from the export cannot be shown.
    function fallBackToServer(id) {
        if (location.protocol !== "http:" && location.protocol !== "https:") {
            console.warn(`Astronaut ${id} is not in the embedded history; nothing to show.`);
            return false;
        }
        location.assign(`?astronaut_id=${id}`);
        return true;
    }

    function switchTo(value, { push = true } = {}) {
        const id = toId(value);
        if (id === null) return false;
        if (id === current) {
            closeCrewPage();
            return true;
        }
        if (!inHistory(id)) return fallBackToServer(id);

        current = id;
        if (push) pushUrl(id);
        document.dispatchEvent(new CustomEvent(EVENT, { detail: { astronautId: id } }));
        restartSwitchAnimation();
        markCurrent();
        announce(id);
        closeCrewPage();
        return true;
    }

    function onCardClick(event) {
        const modified = event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
        if (event.defaultPrevented || event.button !== 0 || modified) return;
        const id = cardId(event.currentTarget);
        if (id === null) return;
        event.preventDefault();
        switchTo(id);
    }

    // Links activate on Enter natively; Space needs this.
    function onCardKeyDown(event) {
        if (event.key !== " ") return;
        event.preventDefault();
        const id = cardId(event.currentTarget);
        if (id !== null) switchTo(id);
    }

    function onPopState(event) {
        const fromUrl = toId(new URLSearchParams(location.search).get("astronaut_id"));
        const id = toId(event.state?.astronautId) ?? fromUrl ?? historyAstronauts()[0]?.id ?? null;
        if (id !== null) switchTo(id, { push: false });
    }

    cards.forEach((card, index) => {
        prepareCard(card, index);
        card.addEventListener("click", onCardClick);
        card.addEventListener("keydown", onCardKeyDown);
    });

    current = initialId();
    markCurrent();
    if (current !== null) replaceUrlState(current);
    window.addEventListener("popstate", onPopState);

    window.MedPointAstronaut = Object.freeze({
        current: () => current,
        switchTo
    });
})();
