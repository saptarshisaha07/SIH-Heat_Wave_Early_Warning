/**
 * Forecast Chart & Visualizations module for Bhubaneswar Heatwave Early Warning System.
 * Renders multi-horizon Heat Index forecast line charts with risk-zone background bands,
 * dark-theme styling, and the horizontal composite score gradient gauge bar.
 */

// Module-level reference to the active Chart.js instance to prevent memory leaks and orphaned canvases
let currentForecastChartInstance = null;

/**
 * Maps risk categories and alert levels to their authoritative hex color codes.
 * Matches the color palette established in map.js and backend risk engine.
 *
 * @param {string} category - Risk category or alert level name
 * @returns {string} Hex color code
 */
function getRiskCategoryColor(category) {
    if (!category || typeof category !== 'string') {
        return '#28a745';
    }

    const normalized = category.trim().toLowerCase();
    const colorMap = {
        'green': '#28a745',
        'normal': '#28a745',
        'yellow': '#ffc107',
        'caution': '#ffc107',
        'orange': '#fd7e14',
        'extreme caution': '#fd7e14',
        'red': '#dc3545',
        'danger': '#dc3545',
        'maroon': '#800000',
        'extreme danger': '#800000'
    };

    return colorMap[normalized] || '#28a745';
}

/**
 * Renders a horizontal gradient Composite Risk Score gauge bar with needle pointer and category badge.
 * Built with pure DOM elements for high performance and pixel-accurate placement.
 *
 * @param {number|string} score - Risk score value (0-100 continuous)
 * @param {string} category - Risk category name (Normal, Caution, Extreme Caution, Danger, Extreme Danger)
 * @param {HTMLElement} containerElement - Parent DOM element where gauge should be appended
 */
function renderScoreGauge(score, category, containerElement) {
    if (!containerElement) return;

    // Parse numeric score, clamped 0-100
    const numScore = (score !== null && score !== undefined && !isNaN(Number(score)))
        ? Math.max(0, Math.min(100, Number(score)))
        : 0;
    const displayScore = (score !== null && score !== undefined && !isNaN(Number(score)))
        ? Number(score).toFixed(1)
        : 'N/A';
    const safeCategory = category || 'Normal';
    const categoryColor = getRiskCategoryColor(safeCategory);

    const gaugeContainer = document.createElement('div');
    gaugeContainer.className = 'score-gauge-container';

    // Header with title and colored badge
    const headerDiv = document.createElement('div');
    headerDiv.className = 'score-gauge-header';

    const titleSpan = document.createElement('span');
    titleSpan.className = 'score-gauge-title';
    titleSpan.textContent = 'Risk Level Gauge';
    headerDiv.appendChild(titleSpan);

    const badge = document.createElement('span');
    badge.className = 'score-gauge-badge';
    badge.style.backgroundColor = categoryColor;
    badge.textContent = `${displayScore} — ${safeCategory}`;
    headerDiv.appendChild(badge);

    gaugeContainer.appendChild(headerDiv);

    // Bar wrapper with gradient track and positioned pointer
    const barWrapper = document.createElement('div');
    barWrapper.className = 'score-gauge-bar-wrapper';

    const bar = document.createElement('div');
    bar.className = 'score-gauge-bar';
    barWrapper.appendChild(bar);

    // Positioned needle pointer
    const pointer = document.createElement('div');
    pointer.className = 'score-gauge-pointer';
    pointer.style.left = `${numScore}%`;

    const needle = document.createElement('div');
    needle.className = 'score-gauge-pointer-needle';
    pointer.appendChild(needle);

    const pin = document.createElement('div');
    pin.className = 'score-gauge-pointer-pin';
    pointer.appendChild(pin);

    barWrapper.appendChild(pointer);
    gaugeContainer.appendChild(barWrapper);

    // Scale ticks below bar
    const ticks = document.createElement('div');
    ticks.className = 'score-gauge-scale-ticks';

    const tick0 = document.createElement('span');
    tick0.textContent = '0 (Low)';
    const tick20 = document.createElement('span');
    tick20.textContent = '20';
    const tick40 = document.createElement('span');
    tick40.textContent = '40';
    const tick60 = document.createElement('span');
    tick60.textContent = '60';
    const tick85 = document.createElement('span');
    tick85.textContent = '85';
    const tick100 = document.createElement('span');
    tick100.textContent = '100 (Severe)';

    ticks.appendChild(tick0);
    ticks.appendChild(tick20);
    ticks.appendChild(tick40);
    ticks.appendChild(tick60);
    ticks.appendChild(tick85);
    ticks.appendChild(tick100);

    gaugeContainer.appendChild(ticks);

    containerElement.appendChild(gaugeContainer);
}

/**
 * Custom inline Chart.js plugin to render subtle colored risk-zone background bands
 * behind the forecast line chart across Heat Index severity intervals.
 */
const riskZoneBandsPlugin = {
    id: 'riskZoneBands',
    beforeDraw: (chart) => {
        const { ctx, chartArea, scales: { y } } = chart;
        if (!chartArea || !y) return;

        // Meteorological Heat Index bands (°C):
        // <27°C: Normal (green)
        // 27-32°C: Caution (yellow)
        // 33-41°C: Extreme Caution (orange)
        // 42-54°C: Danger (red)
        // 55°C+: Extreme Danger (maroon)
        const zones = [
            { min: 0, max: 27, color: 'rgba(40, 167, 69, 0.09)' },
            { min: 27, max: 33, color: 'rgba(255, 193, 7, 0.09)' },
            { min: 33, max: 42, color: 'rgba(253, 126, 20, 0.09)' },
            { min: 42, max: 54, color: 'rgba(220, 53, 69, 0.09)' },
            { min: 54, max: 100, color: 'rgba(128, 0, 0, 0.09)' }
        ];

        ctx.save();
        zones.forEach(zone => {
            const yTop = Math.max(chartArea.top, y.getPixelForValue(zone.max));
            const yBottom = Math.min(chartArea.bottom, y.getPixelForValue(zone.min));
            if (yBottom > yTop && yBottom >= chartArea.top && yTop <= chartArea.bottom) {
                ctx.fillStyle = zone.color;
                ctx.fillRect(chartArea.left, yTop, chartArea.right - chartArea.left, yBottom - yTop);
            }
        });
        ctx.restore();
    }
};

/**
 * Renders a Heat Index forecast line chart inside the specified container element.
 * Re-themed for dark background with cyan glow line and risk-zone bands.
 *
 * @param {Array<Object>} forecastArray - Array of forecast objects with date, predicted_heat_index, predicted_risk_category
 * @param {HTMLElement} containerElement - DOM element container where the chart/message should be appended
 */
function renderForecastChart(forecastArray, containerElement) {
    // 1. Destroy any existing Chart instance before DOM modifications to prevent leaks
    if (currentForecastChartInstance) {
        currentForecastChartInstance.destroy();
        currentForecastChartInstance = null;
    }

    if (!containerElement) {
        return;
    }

    // 2. Handle missing or empty forecast data gracefully
    if (!Array.isArray(forecastArray) || forecastArray.length === 0) {
        const placeholder = document.createElement('p');
        placeholder.className = 'placeholder-text';
        placeholder.textContent = 'No forecast available.';
        containerElement.appendChild(placeholder);
        return;
    }

    // 3. Create a new canvas element dynamically
    const canvas = document.createElement('canvas');
    containerElement.appendChild(canvas);

    // 4. Extract dates, heat index values, and risk color mappings
    const labels = forecastArray.map(item => (item && item.date) ? String(item.date) : 'N/A');
    const dataPoints = forecastArray.map(item => {
        if (item && item.predicted_heat_index !== undefined && item.predicted_heat_index !== null) {
            return Number(item.predicted_heat_index);
        }
        return null;
    });
    const pointColors = forecastArray.map(item => {
        const cat = item && item.predicted_risk_category ? item.predicted_risk_category : 'Normal';
        return getRiskCategoryColor(cat);
    });

    // 5. Initialize Chart.js line chart instance
    if (typeof Chart === 'undefined') {
        const errorP = document.createElement('p');
        errorP.className = 'sidebar-error';
        errorP.textContent = 'Chart library failed to load.';
        containerElement.appendChild(errorP);
        return;
    }

    currentForecastChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Predicted Heat Index (°C)',
                    data: dataPoints,
                    borderColor: '#38bdf8',
                    borderWidth: 2.5,
                    backgroundColor: 'rgba(56, 189, 248, 0.12)',
                    pointBackgroundColor: pointColors,
                    pointBorderColor: '#0f172a',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        plugins: [riskZoneBandsPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: function (context) {
                            const index = context.dataIndex;
                            const item = forecastArray[index];
                            const risk = item && item.predicted_risk_category ? item.predicted_risk_category : 'N/A';
                            const val = context.parsed.y !== null && context.parsed.y !== undefined ? context.parsed.y : 'N/A';
                            return `Heat Index: ${val} °C (${risk})`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Forecast Date',
                        font: {
                            size: 11,
                            weight: '600'
                        },
                        color: '#94a3b8'
                    },
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            size: 10
                        },
                        color: '#94a3b8'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Predicted Heat Index (°C)',
                        font: {
                            size: 11,
                            weight: '600'
                        },
                        color: '#94a3b8'
                    },
                    ticks: {
                        font: {
                            size: 10
                        },
                        color: '#94a3b8',
                        callback: function (val) {
                            return `${val} °C`;
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.07)'
                    }
                }
            }
        }
    });
}

// Expose functions globally on window for app.js
window.renderForecastChart = renderForecastChart;
window.renderScoreGauge = renderScoreGauge;
window.getRiskCategoryColor = getRiskCategoryColor;

