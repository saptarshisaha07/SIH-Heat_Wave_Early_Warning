/**
 * Forecast Chart module for Bhubaneswar Heatwave Early Warning System.
 * Renders multi-horizon Heat Index forecast line charts using Chart.js with
 * risk-category-based point color coding and strict instance lifecycle management.
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
 * Renders a Heat Index forecast line chart inside the specified container element.
 * Manages canvas creation, data extraction, color mapping, and chart lifecycle.
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
                    borderColor: '#3182ce',
                    borderWidth: 2,
                    backgroundColor: 'rgba(49, 130, 206, 0.08)',
                    pointBackgroundColor: pointColors,
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    fill: true,
                    tension: 0.25
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
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
                        color: '#718096'
                    },
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            size: 10
                        },
                        color: '#4a5568'
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
                        color: '#718096'
                    },
                    ticks: {
                        font: {
                            size: 10
                        },
                        color: '#4a5568',
                        callback: function (val) {
                            return `${val} °C`;
                        }
                    },
                    grid: {
                        color: '#edf2f7'
                    }
                }
            }
        }
    });
}

// Expose render function globally on window for app.js
window.renderForecastChart = renderForecastChart;
window.getRiskCategoryColor = getRiskCategoryColor;
