/* -----------------------------------
   Med-Point | crew model loading
   Loads the crew 3D models one at a time, after the crew page zoom, so the
   zoom does not stutter while 70 MB of models download and decode.
   ----------------------------------- */

(function setupCrewModelLoading() {
    "use strict";

    // The zoom takes 720ms (Aspect MIP.css); this is the fallback if transitionend never fires.
    const ZOOM_FALLBACK_MS = 800;
    // Longest wait for one model before moving on, so a stuck model cannot block the rest.
    const MODEL_TIMEOUT_MS = 20000;

    const loadModel = window.MedPointModels?.loadModel;
    const button = document.getElementById("openColleaguesPage");
    const page = document.getElementById("colleaguesDetailPage");

    if (typeof loadModel !== "function" || !button || !page) return;

    // The card the visitor is on goes first, then the rest in page order.
    function crewViewers() {
        const all = Array.from(document.querySelectorAll(".crew-model"));
        const current = document.querySelector('.crew-card[aria-current="true"] .crew-model');
        if (!current) return all;
        return [current, ...all.filter((viewer) => viewer !== current)];
    }

    // Calls onDone once the viewer's loader is hidden (loaded or failed), or on timeout.
    function waitForModel(viewer, onDone) {
        const loader = viewer.parentElement?.querySelector(".model-loading") ?? null;
        let observer = null;
        let timer = 0;
        let finished = false;

        function finish() {
            if (finished) return;
            finished = true;
            observer?.disconnect();
            window.clearTimeout(timer);
            viewer.removeEventListener("load", finish);
            viewer.removeEventListener("error", finish);
            onDone();
        }

        timer = window.setTimeout(finish, MODEL_TIMEOUT_MS);

        if (!loader) {
            viewer.addEventListener("load", finish);
            viewer.addEventListener("error", finish);
            return;
        }

        observer = new MutationObserver(() => {
            if (loader.classList.contains("is-done")) finish();
        });
        observer.observe(loader, { attributes: true, attributeFilter: ["class"] });
        if (loader.classList.contains("is-done")) finish();
    }

    // Starts the model at `index` and moves on only when it has finished.
    function loadNext(viewers, index) {
        if (index >= viewers.length) return;
        const viewer = viewers[index];
        waitForModel(viewer, () => loadNext(viewers, index + 1));
        loadModel(viewer);
    }

    function onZoomDone() {
        loadNext(crewViewers(), 0);
    }

    function onFirstOpen() {
        let timer = 0;

        // Runs once: whichever of transitionend or the fallback timer comes first.
        function start() {
            page.removeEventListener("transitionend", onTransitionEnd);
            window.clearTimeout(timer);
            onZoomDone();
        }

        function onTransitionEnd(event) {
            if (event.target === page && event.propertyName === "clip-path") start();
        }

        // If the page is already open, its zoom has run or is running, so only the timer is used.
        if (!page.classList.contains("is-open")) {
            page.addEventListener("transitionend", onTransitionEnd);
        }
        timer = window.setTimeout(start, ZOOM_FALLBACK_MS);
    }

    button.addEventListener("click", onFirstOpen, { once: true });
})();
