const API_BASE_URL = window.location.origin;
const ROARING_LION_FROM_DATE = "2026-02-28";
const MODE_STORAGE_KEY = "redalert-dashboard-mode";
const ISRAEL_VIEW = {
    center: [31.45, 34.85],
    zoom: 8,
};

const DASHBOARD_MODES = {
    default: {
        key: "default",
        themeColor: "#eef3f0",
        fromDate: null,
        primaryLabel: "Today",
        lede: "A minimal frontend for the RedAlert API. It keeps the map front and center, surfaces only the key daily numbers, and lets you inspect the main hotspots without burying the page in controls.",
        areaHitsNote: "Rolled up from today's alert records",
        mapTitle: "Alert markers across mapped cities",
        notesText: "The backend may refresh recent alerts automatically when the newest stored alert is less than one minute old.",
    },
    lion: {
        key: "lion",
        themeColor: "#fbf0de",
        fromDate: ROARING_LION_FROM_DATE,
        primaryLabel: "Roaring Lion",
        lede: "Roaring Lion mode narrows the board to alerts from February 28, 2026 onward and shifts the dashboard into a warmer orange signal palette.",
        areaHitsNote: "Rolled up from alert records since February 28, 2026",
        mapTitle: "Roaring Lion markers since February 28, 2026",
        notesText: "Roaring Lion mode filters the dashboard to alerts from February 28, 2026 onward. The backend may still refresh recent alerts automatically when the newest stored alert is less than one minute old.",
    },
};

const state = {
    summary: null,
    mapSummary: null,
    selectedCityId: null,
    isLoading: false,
    markersById: new Map(),
    hasFittedOnce: false,
    dashboardMode: loadStoredMode(),
};

const elements = {
    themeColorMeta: document.querySelector('meta[name="theme-color"]'),
    lionModeButton: document.querySelector("#lionModeButton"),
    refreshButton: document.querySelector("#refreshButton"),
    fitMapButton: document.querySelector("#fitMapButton"),
    connectionText: document.querySelector("#connectionText"),
    heroLede: document.querySelector("#heroLede"),
    primaryStatLabel: document.querySelector("#primaryStatLabel"),
    todayAlertCount: document.querySelector("#todayAlertCount"),
    todayAreaHits: document.querySelector("#todayAreaHits"),
    trackedCities: document.querySelector("#trackedCities"),
    latestAlertText: document.querySelector("#latestAlertText"),
    areaHitsNote: document.querySelector("#areaHitsNote"),
    datasetLoadedText: document.querySelector("#datasetLoadedText"),
    mapTitle: document.querySelector("#mapTitle"),
    mapMeta: document.querySelector("#mapMeta"),
    notesText: document.querySelector("#notesText"),
    citySpotlight: document.querySelector("#citySpotlight"),
    hotspotList: document.querySelector("#hotspotList"),
    loadingOverlay: document.querySelector("#loadingOverlay"),
};

const map = L.map("map", {
    preferCanvas: true,
    zoomControl: false,
}).setView(ISRAEL_VIEW.center, ISRAEL_VIEW.zoom);

L.control.zoom({ position: "bottomright" }).addTo(map);

L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap &copy; CARTO",
}).addTo(map);

const markerLayer = L.layerGroup().addTo(map);

initialize();

function initialize() {
    applyDashboardMode();
    bindEvents();
    void loadBoard();
}

function bindEvents() {
    elements.lionModeButton.addEventListener("click", () => {
        state.dashboardMode = isLionMode() ? "default" : "lion";
        applyDashboardMode();
        void loadBoard();
    });

    elements.refreshButton.addEventListener("click", () => {
        void loadBoard();
    });

    elements.fitMapButton.addEventListener("click", () => {
        fitToMarkers();
    });
}

async function loadBoard() {
    setLoading(true);
    setConnectionText("Refreshing");
    state.hasFittedOnce = false;

    try {
        const [summary, mapSummary] = await Promise.all([
            fetchJson(buildSummaryUrl()),
            fetchJson(buildMapUrl()),
        ]);

        state.summary = summary;
        state.mapSummary = mapSummary;

        if (!state.selectedCityId && Array.isArray(mapSummary.cities) && mapSummary.cities.length > 0) {
            state.selectedCityId = mapSummary.cities[0].id;
        }

        if (!mapSummary.cities.some((city) => city.id === state.selectedCityId)) {
            state.selectedCityId = mapSummary.cities[0] ? mapSummary.cities[0].id : null;
        }

        renderSummary();
        renderMap();
        renderHotspots();
        renderSpotlight();
        setConnectionText("Live");
    } catch (error) {
        console.error(error);
        renderFailure(error);
        setConnectionText("Offline");
    } finally {
        setLoading(false);
    }
}

function applyDashboardMode() {
    const mode = getDashboardMode();
    const lionActive = isLionMode();

    document.body.classList.toggle("theme-lion", lionActive);
    elements.lionModeButton.setAttribute("aria-pressed", String(lionActive));
    elements.heroLede.textContent = mode.lede;
    elements.primaryStatLabel.textContent = mode.primaryLabel;
    elements.areaHitsNote.textContent = mode.areaHitsNote;
    elements.mapTitle.textContent = mode.mapTitle;
    elements.notesText.textContent = mode.notesText;
    if (elements.themeColorMeta) {
        elements.themeColorMeta.setAttribute("content", mode.themeColor);
    }
    persistDashboardMode(mode.key);

    if (state.summary && state.mapSummary) {
        renderSummary();
        renderMap();
        renderHotspots();
        renderSpotlight();
    }
}

function renderSummary() {
    const summary = state.summary;
    const mapSummary = state.mapSummary;
    if (!summary || !mapSummary) {
        return;
    }

    elements.todayAlertCount.textContent = formatNumber(summary.alert_count);
    elements.todayAreaHits.textContent = formatNumber(summary.area_hit_count);
    elements.trackedCities.textContent = formatNumber(mapSummary.available_cities);
    elements.latestAlertText.textContent = `${isLionMode() ? "Latest in range" : "Latest alert"}: ${formatDateTime(summary.latest_alert_at)}`;
    elements.datasetLoadedText.textContent = `Snapshot loaded ${formatDateTime(mapSummary.dataset_loaded_at)}`;
    elements.mapMeta.textContent = `${formatNumber(mapSummary.returned_cities)} mapped cities, ${formatNumber(mapSummary.unmapped_area_hits)} unmapped hits${formatScopeSuffix()}`;
}

function renderMap() {
    markerLayer.clearLayers();
    state.markersById.clear();

    const cities = getCities();
    if (cities.length === 0) {
        map.setView(ISRAEL_VIEW.center, ISRAEL_VIEW.zoom);
        return;
    }

    const bounds = [];

    for (const city of cities) {
        const marker = L.circleMarker([city.lat, city.lng], {
            radius: markerRadius(city.total_alerts),
            color: city.id === state.selectedCityId ? markerSelectedColor() : markerStrokeColor(),
            weight: city.id === state.selectedCityId ? 2.2 : 1.1,
            fillColor: markerColor(city.total_alerts),
            fillOpacity: city.id === state.selectedCityId ? 0.92 : 0.74,
            opacity: 0.95,
        });

        marker.bindPopup(`
            <div class="map-popup">
                <h4>${escapeHtml(city.name)}</h4>
                <p>${escapeHtml(city.name_he || city.name)}</p>
                <p>${formatCityAlertLabel(city.total_alerts)}</p>
                <p>Last alert ${formatDateTime(city.last_alert_at)}</p>
            </div>
        `);

        marker.on("click", () => {
            selectCity(city.id, false);
        });

        marker.addTo(markerLayer);
        state.markersById.set(city.id, marker);
        bounds.push([city.lat, city.lng]);
    }

    if (!state.hasFittedOnce) {
        fitToMarkers(bounds);
        state.hasFittedOnce = true;
    }

    updateMarkerSelection();
}

function renderHotspots() {
    const cities = getCities();
    elements.hotspotList.innerHTML = "";

    if (cities.length === 0) {
        elements.hotspotList.innerHTML = `<p class="empty-state">No mapped cities were returned for this view.</p>`;
        return;
    }

    for (const city of cities.slice(0, 12)) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `hotspot${city.id === state.selectedCityId ? " hotspot--selected" : ""}`;
        button.innerHTML = `
            <div class="hotspot__head">
                <strong>${escapeHtml(city.name)}</strong>
                <span>${formatNumber(city.total_alerts)}</span>
            </div>
            <div class="hotspot__meta">
                <span>${escapeHtml(city.name_he || city.name)}</span>
                <span>${formatDateTime(city.last_alert_at)}</span>
            </div>
        `;
        button.addEventListener("click", () => {
            selectCity(city.id, true);
        });
        elements.hotspotList.appendChild(button);
    }
}

function renderSpotlight() {
    const city = getCities().find((item) => item.id === state.selectedCityId);
    if (!city) {
        elements.citySpotlight.className = "spotlight empty-state";
        elements.citySpotlight.textContent = "Click a marker to inspect a city.";
        return;
    }

    elements.citySpotlight.className = "spotlight";
    elements.citySpotlight.innerHTML = `
        <div class="spotlight__title">
            <h4>${escapeHtml(city.name)}</h4>
            <p>${escapeHtml(city.name_he || city.name)}</p>
        </div>
        <div class="chip-row">
            <span class="chip">${formatCityAlertLabel(city.total_alerts)}</span>
            <span class="chip">${formatLatLng(city.lat, city.lng)}</span>
        </div>
        <p class="spotlight__meta">Last alert at ${formatDateTime(city.last_alert_at)}</p>
    `;

    updateMarkerSelection();
}

function renderFailure(error) {
    const message = error instanceof Error ? error.message : "Unable to load the backend.";
    elements.citySpotlight.className = "spotlight empty-state";
    elements.citySpotlight.textContent = message;
    elements.hotspotList.innerHTML = `<p class="empty-state">Start the backend and refresh the board.</p>`;
    elements.mapMeta.textContent = "The map snapshot is unavailable right now.";
    markerLayer.clearLayers();
}

function selectCity(cityId, flyToMarker) {
    state.selectedCityId = cityId;
    renderHotspots();
    renderSpotlight();

    const marker = state.markersById.get(cityId);
    if (!marker) {
        return;
    }

    if (flyToMarker) {
        map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 9), {
            duration: 0.75,
        });
    }
    marker.openPopup();
}

function updateMarkerSelection() {
    for (const [cityId, marker] of state.markersById.entries()) {
        const city = getCities().find((item) => item.id === cityId);
        if (!city) {
            continue;
        }

        const selected = cityId === state.selectedCityId;
        marker.setStyle({
            radius: markerRadius(city.total_alerts) + (selected ? 1.4 : 0),
            color: selected ? markerSelectedColor() : markerStrokeColor(),
            weight: selected ? 2.2 : 1.1,
            fillColor: markerColor(city.total_alerts),
            fillOpacity: selected ? 0.92 : 0.74,
        });
    }
}

function getCities() {
    return Array.isArray(state.mapSummary?.cities) ? state.mapSummary.cities : [];
}

function getDashboardMode() {
    return DASHBOARD_MODES[state.dashboardMode] || DASHBOARD_MODES.default;
}

function isLionMode() {
    return state.dashboardMode === "lion";
}

function setLoading(isLoading) {
    state.isLoading = isLoading;
    elements.loadingOverlay.hidden = !isLoading;
    elements.refreshButton.disabled = isLoading;
    elements.lionModeButton.disabled = isLoading;
}

function setConnectionText(text) {
    elements.connectionText.textContent = text;
}

function fitToMarkers(customBounds) {
    const bounds = customBounds || Array.from(state.markersById.values()).map((marker) => {
        const point = marker.getLatLng();
        return [point.lat, point.lng];
    });

    if (bounds.length === 0) {
        map.setView(ISRAEL_VIEW.center, ISRAEL_VIEW.zoom);
        return;
    }

    map.fitBounds(bounds, {
        padding: [34, 34],
        maxZoom: 11,
    });
}

function buildSummaryUrl() {
    const url = buildApiUrl("/api/alerts/summary");
    const fromDate = getDashboardMode().fromDate;
    if (fromDate) {
        url.searchParams.set("from_date", fromDate);
    }
    return url;
}

function buildMapUrl() {
    const url = buildApiUrl("/api/alerts/map");
    const fromDate = getDashboardMode().fromDate;
    if (fromDate) {
        url.searchParams.set("from_date", fromDate);
    }
    return url;
}

function buildApiUrl(path) {
    return new URL(path, `${API_BASE_URL}/`);
}

async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API request failed with ${response.status} ${response.statusText}`);
    }
    return response.json();
}

function markerRadius(totalAlerts) {
    const value = Math.max(1, Number(totalAlerts) || 0);
    return Math.max(5, Math.min(22, 4 + Math.sqrt(value) * 0.68));
}

function markerColor(totalAlerts) {
    const value = Number(totalAlerts) || 0;
    if (isLionMode()) {
        if (value >= 400) {
            return "#a94f07";
        }
        if (value >= 200) {
            return "#cf6f14";
        }
        if (value >= 80) {
            return "#e99943";
        }
        return "#f5c68d";
    }

    if (value >= 400) {
        return "#315a4f";
    }
    if (value >= 200) {
        return "#4d7668";
    }
    if (value >= 80) {
        return "#789d8e";
    }
    return "#c7d9cf";
}

function markerStrokeColor() {
    return getComputedStyle(document.body).getPropertyValue("--marker-stroke").trim() || "#41675a";
}

function markerSelectedColor() {
    return getComputedStyle(document.body).getPropertyValue("--marker-selected").trim() || "#1b2730";
}

function formatCityAlertLabel(totalAlerts) {
    const count = formatNumber(totalAlerts);
    if (!isLionMode()) {
        return `${count} total alerts`;
    }
    return `${count} alerts since ${formatScopeDate(ROARING_LION_FROM_DATE)}`;
}

function formatScopeSuffix() {
    return isLionMode() ? ` since ${formatScopeDate(ROARING_LION_FROM_DATE)}` : "";
}

function formatScopeDate(value) {
    if (!value) {
        return "";
    }

    const [year, month, day] = value.split("-").map((part) => Number(part));
    const date = new Date(year, month - 1, day);
    return new Intl.DateTimeFormat("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric",
    }).format(date);
}

function formatNumber(value) {
    return new Intl.NumberFormat("en-US").format(Number(value) || 0);
}

function formatDateTime(value) {
    if (!value) {
        return "No data";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

function formatLatLng(lat, lng) {
    return `${Number(lat).toFixed(2)}, ${Number(lng).toFixed(2)}`;
}

function loadStoredMode() {
    try {
        const value = window.localStorage.getItem(MODE_STORAGE_KEY);
        return value === "lion" ? "lion" : "default";
    } catch {
        return "default";
    }
}

function persistDashboardMode(mode) {
    try {
        window.localStorage.setItem(MODE_STORAGE_KEY, mode);
    } catch {
        // Ignore storage failures and keep the current in-memory mode.
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
