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

    // Weather & Thermal Conditions
    const weatherSection = document.createElement('div');
    weatherSection.className = 'sidebar-section';

    const weatherTitle = document.createElement('h3');
    weatherTitle.textContent = 'Current Atmospheric Conditions';
    weatherSection.appendChild(weatherTitle);

    weatherSection.appendChild(createDataRow('Temperature', current.temp_c !== undefined ? `${current.temp_c} °C` : 'N/A'));
    weatherSection.appendChild(createDataRow('Relative Humidity', current.humidity_pct !== undefined ? `${current.humidity_pct} %` : 'N/A'));
    weatherSection.appendChild(createDataRow('Wind Speed', current.wind_kmh !== undefined ? `${current.wind_kmh} km/h` : 'N/A'));
    weatherSection.appendChild(createDataRow('Heat Index', current.heat_index !== undefined ? `${current.heat_index} °C` : 'N/A'));
    weatherSection.appendChild(createDataRow('Simplified WBGT', current.wbgt !== undefined ? `${current.wbgt} °C` : 'N/A'));

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
