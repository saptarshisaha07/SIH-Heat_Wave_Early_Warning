/**
 * Application controller for Bhubaneswar Heatwave Early Warning System.
 * Connects Leaflet map marker clicks to the backend API and renders ward risk slice in the sidebar.
 */

let activeRequestId = 0;
let lastSelectedWardData = null;
window.currentScoreMode = 'adjusted';

function getSidebarElement() {
    return document.getElementById('ward-details');
}

/**
 * Displays a visible loading indicator in the sidebar.
 * @param {string|number} wardId
 */
function renderSidebarLoading(wardId) {
    const sidebar = getSidebarElement();
    if (!sidebar) return;

    while (sidebar.firstChild) {
        sidebar.removeChild(sidebar.firstChild);
    }

    const heading = document.createElement('h3');
    heading.textContent = 'Ward Details';
    sidebar.appendChild(heading);

    const loadingP = document.createElement('p');
    loadingP.className = 'sidebar-status loading';
    loadingP.textContent = `Loading live data for ${wardId}...`;
    sidebar.appendChild(loadingP);
}

/**
 * Displays a visible error message in the sidebar if API call fails.
 * @param {string|number} wardId
 * @param {string} errorMessage
 */
function renderSidebarError(wardId, errorMessage) {
    const sidebar = getSidebarElement();
    if (!sidebar) return;

    while (sidebar.firstChild) {
        sidebar.removeChild(sidebar.firstChild);
    }

    const heading = document.createElement('h3');
    heading.textContent = 'Ward Details';
    sidebar.appendChild(heading);

    const errorContainer = document.createElement('div');
    errorContainer.className = 'sidebar-error';
    errorContainer.setAttribute('role', 'alert');

    const errorTitle = document.createElement('strong');
    errorTitle.textContent = `Failed to load ${wardId}: `;
    errorContainer.appendChild(errorTitle);

    const errorMsg = document.createElement('span');
    errorMsg.textContent = errorMessage;
    errorContainer.appendChild(errorMsg);

    sidebar.appendChild(errorContainer);
}

const WEATHER_ICONS = {
    temp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>',
    humidity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>',
    wind: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/></svg>',
    heatIndex: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 3z"/></svg>',
    wbgt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>'
};

/**
 * Helper to construct an atmospheric metric badge tile with visual SVG icon and typography.
 * @param {string} iconSvg - Inline SVG markup
 * @param {string} label - Metric label
 * @param {string|number} value - Formatted value with units
 * @param {string} iconClass - CSS color class for circular icon container
 * @param {boolean} fullWidth - Whether tile spans full grid width
 * @returns {HTMLElement}
 */
function createWeatherMetricTile(iconSvg, label, value, iconClass, fullWidth = false) {
    const tile = document.createElement('div');
    tile.className = 'weather-metric-item' + (fullWidth ? ' full-width' : '');

    const iconBox = document.createElement('div');
    iconBox.className = `weather-metric-icon ${iconClass}`;
    iconBox.innerHTML = iconSvg;

    const contentBox = document.createElement('div');
    contentBox.className = 'weather-metric-text';

    const labelEl = document.createElement('span');
    labelEl.className = 'weather-metric-label';
    labelEl.textContent = label;

    const valueEl = document.createElement('strong');
    valueEl.className = 'weather-metric-value';
    valueEl.textContent = value !== null && value !== undefined ? String(value) : 'N/A';

    contentBox.appendChild(labelEl);
    contentBox.appendChild(valueEl);

    tile.appendChild(iconBox);
    tile.appendChild(contentBox);
    return tile;
}

/**
 * Helper to safely construct a key-value data row.
 * @param {string} label
 * @param {string|number} value
 * @returns {HTMLElement}
 */
function createDataRow(label, value) {
    const row = document.createElement('div');
    row.className = 'data-row';

    const labelSpan = document.createElement('span');
    labelSpan.className = 'data-label';
    labelSpan.textContent = label;

    const valueSpan = document.createElement('span');
    valueSpan.className = 'data-value';
    valueSpan.textContent = value !== null && value !== undefined ? String(value) : 'N/A';

    row.appendChild(labelSpan);
    row.appendChild(valueSpan);
    return row;
}

/**
 * Renders real ward data into the sidebar safely using textContent.
 * @param {Object} data - Full response payload from GET /api/wards/{id}
 */
function renderSidebarData(data) {
    const sidebar = getSidebarElement();
    if (!sidebar || !data) return;

    // Cache latest selected ward data for instant toggle re-rendering
    lastSelectedWardData = data;

    while (sidebar.firstChild) {
        sidebar.removeChild(sidebar.firstChild);
    }

    const ward = data.ward || {};
    const current = data.current || {};
    const isHeatOnly = (window.currentScoreMode === 'heat_only');

    // Header section
    const header = document.createElement('div');
    header.className = 'sidebar-header';

    const title = document.createElement('h2');
    title.textContent = ward.name || 'Ward Details';
    header.appendChild(title);

    if (ward.ward_number) {
        const badge = document.createElement('span');
        badge.className = 'ward-id-badge';
        badge.textContent = `Ward ID: ${ward.ward_number}`;
        header.appendChild(badge);
    }

    sidebar.appendChild(header);

    // Weather & Thermal Conditions (with visual badge icons)
    const weatherSection = document.createElement('div');
    weatherSection.className = 'sidebar-section';

    const weatherTitle = document.createElement('h3');
    weatherTitle.textContent = 'Current Atmospheric Conditions';
    weatherSection.appendChild(weatherTitle);

    const metricsGrid = document.createElement('div');
    metricsGrid.className = 'weather-metrics-grid';

    metricsGrid.appendChild(createWeatherMetricTile(
        WEATHER_ICONS.temp,
        'Temperature',
        current.temp_c !== undefined ? `${current.temp_c} °C` : 'N/A',
        'icon-temp'
    ));

    metricsGrid.appendChild(createWeatherMetricTile(
        WEATHER_ICONS.humidity,
        'Humidity',
        current.humidity_pct !== undefined ? `${current.humidity_pct} %` : 'N/A',
        'icon-humidity'
    ));

    metricsGrid.appendChild(createWeatherMetricTile(
        WEATHER_ICONS.heatIndex,
        'Heat Index',
        current.heat_index !== undefined ? `${current.heat_index} °C` : 'N/A',
        'icon-heat-index'
    ));

    metricsGrid.appendChild(createWeatherMetricTile(
        WEATHER_ICONS.wbgt,
        'Simplified WBGT',
        current.wbgt !== undefined ? `${current.wbgt} °C` : 'N/A',
        'icon-wbgt'
    ));

    metricsGrid.appendChild(createWeatherMetricTile(
        WEATHER_ICONS.wind,
        'Wind Speed',
        current.wind_kmh !== undefined ? `${current.wind_kmh} km/h` : 'N/A',
        'icon-wind',
        true
    ));

    weatherSection.appendChild(metricsGrid);
    sidebar.appendChild(weatherSection);

    // Risk & Vulnerability Profile (Mode-Aware)
    const riskSection = document.createElement('div');
    riskSection.className = 'sidebar-section';

    const riskTitle = document.createElement('h3');
    riskTitle.textContent = 'Risk & Vulnerability Assessment';
    riskSection.appendChild(riskTitle);

    if (isHeatOnly) {
        const heatOnlyScore = current.heat_only_score !== undefined
            ? current.heat_only_score
            : (current.base_score !== undefined ? current.base_score : 'N/A');
        const heatOnlyCat = current.heat_only_risk_category || 'N/A';

        riskSection.appendChild(createDataRow('Heat-Only Risk Score', heatOnlyScore));
        riskSection.appendChild(createDataRow('Heat-Only Risk Category', heatOnlyCat));
        riskSection.appendChild(createDataRow('Evaluation Mode', 'Heat-Only (Vulnerability Excluded)'));
        riskSection.appendChild(createDataRow('Base Heat Score', current.base_score !== undefined ? current.base_score : 'N/A'));
    } else {
        riskSection.appendChild(createDataRow('Composite Risk Score', current.composite_score !== undefined ? current.composite_score : 'N/A'));
        riskSection.appendChild(createDataRow('Risk Category', current.risk_category || 'N/A'));
        riskSection.appendChild(createDataRow('Base Heat Score', current.base_score !== undefined ? current.base_score : 'N/A'));
        riskSection.appendChild(createDataRow('Vulnerability Adjustment', current.vulnerability_adjustment !== undefined ? current.vulnerability_adjustment : 'N/A'));
        riskSection.appendChild(createDataRow('Vulnerability Index', ward.vulnerability_index !== undefined ? ward.vulnerability_index : 'N/A'));
    }

    if (ward.elderly_pct !== undefined && ward.elderly_pct !== null) {
        riskSection.appendChild(createDataRow('Elderly Population', `${ward.elderly_pct} %`));
    }
    if (ward.outdoor_worker_pct !== undefined && ward.outdoor_worker_pct !== null) {
        riskSection.appendChild(createDataRow('Outdoor Worker Population', `${ward.outdoor_worker_pct} %`));
    }

    // Render Composite / Mode-Aware Risk Score Gauge Bar Component
    if (typeof window.renderScoreGauge === 'function') {
        const activeScore = isHeatOnly
            ? (current.heat_only_score !== undefined ? current.heat_only_score : current.base_score)
            : current.composite_score;
        const activeCat = isHeatOnly
            ? (current.heat_only_risk_category || 'Normal')
            : (current.risk_category || 'Normal');
        window.renderScoreGauge(activeScore, activeCat, riskSection);
    }

    sidebar.appendChild(riskSection);

    // Multi-Horizon Forecast Section
    const forecastSection = document.createElement('div');
    forecastSection.className = 'sidebar-section';

    const forecastTitle = document.createElement('h3');
    forecastTitle.textContent = '3–5 Day Forecast';
    forecastSection.appendChild(forecastTitle);

    sidebar.appendChild(forecastSection);

    if (typeof window.renderForecastChart === 'function') {
        window.renderForecastChart(data.forecast, forecastSection);
    }

    // Public Health Advisory Section
    const advisorySection = document.createElement('div');
    advisorySection.className = 'sidebar-section';

    const advisoryTitle = document.createElement('h3');
    advisoryTitle.textContent = 'Public Health Advisory';
    advisorySection.appendChild(advisoryTitle);

    sidebar.appendChild(advisorySection);

    if (typeof window.renderAdvisoryText === 'function') {
        window.renderAdvisoryText(data.advisory, advisorySection);
    }

    // Score Breakdown Section
    const breakdownSection = document.createElement('div');
    breakdownSection.className = 'sidebar-section';

    const breakdownTitle = document.createElement('h3');
    breakdownTitle.textContent = 'Score Breakdown';
    breakdownSection.appendChild(breakdownTitle);

    sidebar.appendChild(breakdownSection);

    if (typeof window.renderScoreBreakdownChart === 'function') {
        window.renderScoreBreakdownChart(data.current, breakdownSection);
    }

    // Send Alert Section
    const alertSection = document.createElement('div');
    alertSection.className = 'sidebar-section';

    const alertTitle = document.createElement('h3');
    alertTitle.textContent = 'Send Alert';
    alertSection.appendChild(alertTitle);

    sidebar.appendChild(alertSection);

    if (typeof window.renderAlertButton === 'function') {
        window.renderAlertButton(data.ward, alertSection);
    }
}

/**
 * Handles marker click event from map.
 * Enforces race condition protection via request sequencing.
 * @param {string|number} wardId
 */
async function handleWardMarkerClick(wardId) {
    const requestId = ++activeRequestId;
    renderSidebarLoading(wardId);

    try {
        const data = await window.getWardDetails(wardId);
        // Prevent stale results from overwriting if a newer click was made
        if (requestId !== activeRequestId) {
            return;
        }
        renderSidebarData(data);
    } catch (error) {
        if (requestId !== activeRequestId) {
            return;
        }
        renderSidebarError(wardId, error.message || 'Unknown error occurred.');
    }
}

/**
 * Global switcher for Risk Evaluation Mode ('adjusted' vs 'heat_only').
 * @param {string} mode
 */
function setScoreMode(mode) {
    const normalizedMode = mode === 'heat_only' ? 'heat_only' : 'adjusted';
    window.currentScoreMode = normalizedMode;

    const btnAdjusted = document.getElementById('toggle-adjusted');
    const btnHeatOnly = document.getElementById('toggle-heat-only');

    if (btnAdjusted && btnHeatOnly) {
        if (normalizedMode === 'heat_only') {
            btnAdjusted.classList.remove('active');
            btnHeatOnly.classList.add('active');
        } else {
            btnAdjusted.classList.add('active');
            btnHeatOnly.classList.remove('active');
        }
    }

    // Update map marker colors in place
    if (typeof window.updateMapMarkerMode === 'function') {
        window.updateMapMarkerMode(normalizedMode);
    }

    // Re-render sidebar if a ward is selected
    if (lastSelectedWardData) {
        renderSidebarData(lastSelectedWardData);
    }
}

// Expose globally on window
window.handleWardMarkerClick = handleWardMarkerClick;
window.setScoreMode = setScoreMode;

// Bind toggle button click handlers on page load
document.addEventListener('DOMContentLoaded', () => {
    const btnAdjusted = document.getElementById('toggle-adjusted');
    const btnHeatOnly = document.getElementById('toggle-heat-only');

    if (btnAdjusted) {
        btnAdjusted.addEventListener('click', () => setScoreMode('adjusted'));
    }
    if (btnHeatOnly) {
        btnHeatOnly.addEventListener('click', () => setScoreMode('heat_only'));
    }
});
