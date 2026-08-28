/**
 * Public Health Advisory and Score Breakdown module for Bhubaneswar Heatwave Early Warning System.
 * Renders structured advisory guidance and a 3-bar score breakdown chart with strict Chart.js
 * instance lifecycle management.
 */

// Module-level reference to the active Breakdown Chart.js instance to prevent memory leaks and orphaned canvases
let currentBreakdownChartInstance = null;

/**
 * Renders plain-language public health advisory headline and actionable items.
 *
 * @param {Object} advisoryObj - Advisory payload object with headline and actions list
 * @param {HTMLElement} containerElement - DOM element container where advisory should be appended
 */
function renderAdvisoryText(advisoryObj, containerElement) {
    if (!containerElement) {
        return;
    }

    // 1. Fallback if advisory payload or headline is missing
    if (!advisoryObj || !advisoryObj.headline || typeof advisoryObj.headline !== 'string' || !advisoryObj.headline.trim()) {
        const placeholder = document.createElement('p');
        placeholder.className = 'placeholder-text';
        placeholder.textContent = 'No advisory available for this ward.';
        containerElement.appendChild(placeholder);
        return;
    }

    // 2. Append prominent headline
    const headlineP = document.createElement('p');
    headlineP.className = 'advisory-headline';

    const strongText = document.createElement('strong');
    strongText.textContent = advisoryObj.headline.trim();
    headlineP.appendChild(strongText);

    containerElement.appendChild(headlineP);

    // 3. Resolve actions list (support actions array with fallback to general_public cohort)
    const rawActions = Array.isArray(advisoryObj.actions)
        ? advisoryObj.actions
        : (Array.isArray(advisoryObj.general_public) ? advisoryObj.general_public : []);

    if (rawActions.length > 0) {
        const ul = document.createElement('ul');
        ul.className = 'advisory-actions-list';

        rawActions.forEach(action => {
            if (action && typeof action === 'string' && action.trim()) {
                const li = document.createElement('li');
                li.className = 'advisory-action-item';
                li.textContent = action.trim();
                ul.appendChild(li);
            }
        });

        if (ul.hasChildNodes()) {
            containerElement.appendChild(ul);
        }
    }
}

/**
 * Renders a 3-bar Chart.js score breakdown bar chart representing Base Heat Score,
 * Vulnerability Adjustment, and Final Composite Risk Score.
 *
 * @param {Object} current - Current ward risk metrics object (base_score, vulnerability_adjustment, composite_score)
 * @param {HTMLElement} containerElement - DOM element container where the chart/message should be appended
 */
function renderScoreBreakdownChart(current, containerElement) {
    // 1. Destroy any existing Chart instance before DOM modifications to prevent memory leaks
    if (currentBreakdownChartInstance) {
        currentBreakdownChartInstance.destroy();
        currentBreakdownChartInstance = null;
    }

    if (!containerElement) {
        return;
    }

    // 2. Handle missing or completely null score data gracefully
    const hasBase = current && current.base_score !== undefined && current.base_score !== null;
    const hasVuln = current && current.vulnerability_adjustment !== undefined && current.vulnerability_adjustment !== null;
    const hasComp = current && current.composite_score !== undefined && current.composite_score !== null;

    if (!current || (!hasBase && !hasVuln && !hasComp)) {
        const placeholder = document.createElement('p');
        placeholder.className = 'placeholder-text';
        placeholder.textContent = 'No score breakdown available.';
        containerElement.appendChild(placeholder);
        return;
    }

    // 3. Check for Chart.js availability
    if (typeof Chart === 'undefined') {
        const errorP = document.createElement('p');
        errorP.className = 'sidebar-error';
        errorP.textContent = 'Chart library failed to load.';
        containerElement.appendChild(errorP);
        return;
    }

    // 4. Create canvas element dynamically
    const canvas = document.createElement('canvas');
    containerElement.appendChild(canvas);

    // 5. Extract numeric score components, treating missing elements as 0
    const baseScore = hasBase ? Number(current.base_score) : 0;
    const vulnAdj = hasVuln ? Number(current.vulnerability_adjustment) : 0;
    const compositeScore = hasComp ? Number(current.composite_score) : 0;

    // 6. Resolve colors: distinct base/adjustment colors, with dynamic risk category color for composite bar
    const baseColor = '#38bdf8'; // Theme Cyan/Blue
    const vulnColor = '#a855f7'; // Vibrant Purple
    let compositeColor = '#ef4444'; // Fallback Red

    if (typeof window.getRiskCategoryColor === 'function' && current.risk_category) {
        compositeColor = window.getRiskCategoryColor(current.risk_category);
    }

    // 7. Instantiate Chart.js bar chart with dark-theme styling
    currentBreakdownChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: ['Base Heat Score', 'Vulnerability Adj.', 'Final Composite Score'],
            datasets: [
                {
                    label: 'Score Value',
                    data: [baseScore, vulnAdj, compositeScore],
                    backgroundColor: [
                        'rgba(56, 189, 248, 0.85)',
                        'rgba(168, 85, 247, 0.85)',
                        compositeColor
                    ],
                    borderColor: [
                        '#38bdf8',
                        '#a855f7',
                        compositeColor
                    ],
                    borderWidth: 1.5,
                    borderRadius: 6
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
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    borderWidth: 1,
                    padding: 10,
                    callbacks: {
                        label: function (context) {
                            const val = context.parsed.y !== null && context.parsed.y !== undefined ? context.parsed.y : 'N/A';
                            return 'Score: ' + val;
                        }
                    }
                }
            },
            scales: {
                x: {
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
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Score Value (0–100)',
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
                        color: '#94a3b8'
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
window.renderAdvisoryText = renderAdvisoryText;
window.renderScoreBreakdownChart = renderScoreBreakdownChart;
