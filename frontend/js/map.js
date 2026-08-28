// Bhubaneswar coordinates
const BHUBANESWAR_COORDS = [20.2961, 85.8245];
const INITIAL_ZOOM = 12;
const GEOJSON_URL = '/api/risk-map';

const CARTO_API_KEY = 'cb1_2hv1_1_c5c94b5aadeaa289343a7178';

let geojsonLayerInstance = null;

function showError(message) {
    console.error(message);
    const errorEl = document.getElementById('error-message');
    if (errorEl) {
        errorEl.textContent = 'Error loading ward data: ' + message;
        errorEl.style.display = 'block';
    }
}

/**
 * Resolves current mode color, risk category, and score for a ward feature.
 * @param {Object} props - Feature properties
 * @param {string} mode - 'adjusted' or 'heat_only'
 * @returns {Object} { color, riskCategory, riskScore }
 */
function getMarkerDisplayData(props, mode) {
    const isHeatOnly = (mode || window.currentScoreMode) === 'heat_only';
    const color = isHeatOnly
        ? (props.heat_only_color || props.color || '#28a745')
        : (props.color || '#28a745');
    const riskCategory = isHeatOnly
        ? (props.heat_only_risk_category || props.heat_only_category || props.risk_category || 'Normal')
        : (props.risk_category || 'Normal');
    const riskScore = isHeatOnly
        ? (props.heat_only_score !== undefined ? props.heat_only_score : props.risk_score)
        : (props.risk_score !== undefined ? props.risk_score : 'N/A');

    return { color, riskCategory, riskScore, isHeatOnly };
}

/**
 * Constructs HTML tooltip content for a ward marker.
 */
function createTooltipContent(wardId, wardName, riskCategory, riskScore, color, isHeatOnly) {
    return `
        <div class="ward-tooltip">
            <strong>${wardId}: ${wardName}</strong><br>
            ${isHeatOnly ? 'Heat-Only Risk' : 'Risk'}: <span style="color: ${color}; font-weight: 700;">${riskCategory}</span> (${riskScore})
        </div>
    `;
}

/**
 * Helper to apply dynamic glowing drop-shadow to Leaflet circle marker SVG paths.
 * @param {L.CircleMarker} layer
 * @param {string} color
 * @param {boolean} isHovered
 */
function applyMarkerGlow(layer, color, isHovered = false) {
    if (layer && layer._path) {
        const spread = isHovered ? '0 0 16px ' : '0 0 10px ';
        layer._path.style.filter = `drop-shadow(${spread}${color})`;
        layer._path.style.transition = 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
    }
}

/**
 * Updates existing Leaflet circle markers in place without removing or re-adding layers.
 * @param {string} mode - 'adjusted' or 'heat_only'
 */
function updateMapMarkerMode(mode) {
    if (!geojsonLayerInstance) return;

    geojsonLayerInstance.eachLayer(layer => {
        const props = (layer.feature && layer.feature.properties) ? layer.feature.properties : {};
        const wardId = props.id || 'Unknown';
        const wardName = props.name || 'Unknown';
        const { color, riskCategory, riskScore, isHeatOnly } = getMarkerDisplayData(props, mode);

        // 1. Update marker color style in place
        layer.setStyle({
            fillColor: color
        });
        applyMarkerGlow(layer, color, false);

        // 2. Update tooltip content in place
        const tooltipHtml = createTooltipContent(wardId, wardName, riskCategory, riskScore, color, isHeatOnly);
        layer.setTooltipContent(tooltipHtml);
    });
}

// Expose globally for toggle switch
window.updateMapMarkerMode = updateMapMarkerMode;

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Leaflet map
    const map = L.map('map').setView(BHUBANESWAR_COORDS, INITIAL_ZOOM);

    // 2. Add Dark Cartography tiles (uses native CARTO Dark Matter when CARTO_API_KEY is provided)
    const isCartoActive = Boolean(CARTO_API_KEY && CARTO_API_KEY.trim().length > 0);
    const tileUrl = isCartoActive
        ? `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY.trim()}`
        : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

    const tileOptions = {
        maxZoom: 20,
        subdomains: 'abcd',
        attribution: isCartoActive
            ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        className: isCartoActive ? '' : 'dark-map-tiles'
    };

    L.tileLayer(tileUrl, tileOptions).addTo(map);

    // 3. Add Dark Themed Legend Control
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = function () {
        const div = L.DomUtil.create('div', 'map-legend');
        div.innerHTML = `
            <div class="legend-title">Risk Scale</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #28a745; box-shadow: 0 0 8px #28a745;"></span> Normal (&lt;20)</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #ffc107; box-shadow: 0 0 8px #ffc107;"></span> Caution (20–39)</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #fd7e14; box-shadow: 0 0 8px #fd7e14;"></span> Extreme Caution (40–59)</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #dc3545; box-shadow: 0 0 8px #dc3545;"></span> Danger (60–84)</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #800000; box-shadow: 0 0 8px #800000;"></span> Extreme Danger (≥85)</div>
        `;
        return div;
    };
    legend.addTo(map);

    // 4. Fetch GeoJSON ward data from /api/risk-map
    fetch(GEOJSON_URL)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch ${GEOJSON_URL} (Status: ${response.status} ${response.statusText})`);
            }
            return response.json();
        })
        .then(data => {
            // Validate GeoJSON FeatureCollection
            if (!data || data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
                throw new Error('Invalid GeoJSON format: Expected a FeatureCollection with a features array.');
            }

            const featureCount = data.features.length;
            if (featureCount < 8 || featureCount > 15) {
                throw new Error(`Invalid feature count: Expected between 8 and 15 features, but got ${featureCount}.`);
            }

            // 5. Render Choropleth markers using circleMarker with glowing dark-theme styles
            geojsonLayerInstance = L.geoJSON(data, {
                pointToLayer: (feature, latlng) => {
                    const props = feature.properties || {};
                    const wardId = props.id || 'Unknown';
                    const wardName = props.name || 'Unknown';
                    const { color, riskCategory, riskScore, isHeatOnly } = getMarkerDisplayData(props, window.currentScoreMode || 'adjusted');

                    const marker = L.circleMarker(latlng, {
                        radius: 12,
                        fillColor: color,
                        color: '#ffffff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9,
                        className: 'ward-circle-marker'
                    });

                    // Bind interactive hover tooltip
                    const tooltipContent = createTooltipContent(wardId, wardName, riskCategory, riskScore, color, isHeatOnly);
                    marker.bindTooltip(tooltipContent, {
                        direction: 'top',
                        offset: [0, -10],
                        opacity: 0.95
                    });

                    // Hover effects: highlight marker & intensify glow
                    marker.on('mouseover', function () {
                        this.setRadius(15);
                        this.setStyle({ weight: 3, fillOpacity: 1 });
                        const currentProps = (this.feature && this.feature.properties) ? this.feature.properties : {};
                        const { color: currentColor } = getMarkerDisplayData(currentProps, window.currentScoreMode);
                        applyMarkerGlow(this, currentColor, true);
                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                            this.bringToFront();
                        }
                    });

                    marker.on('mouseout', function () {
                        this.setRadius(12);
                        this.setStyle({ weight: 2, fillOpacity: 0.9 });
                        const currentProps = (this.feature && this.feature.properties) ? this.feature.properties : {};
                        const { color: currentColor } = getMarkerDisplayData(currentProps, window.currentScoreMode);
                        applyMarkerGlow(this, currentColor, false);
                    });

                    // Click handler: trigger sidebar update
                    marker.on('click', () => {
                        console.log(`Clicked ward: ${wardId}`);
                        if (typeof window.handleWardMarkerClick === 'function') {
                            window.handleWardMarkerClick(wardId);
                        }
                    });

                    return marker;
                }
            }).addTo(map);

            // Apply initial glowing drop-shadow once markers are in DOM
            setTimeout(() => {
                if (geojsonLayerInstance) {
                    geojsonLayerInstance.eachLayer(layer => {
                        const props = (layer.feature && layer.feature.properties) ? layer.feature.properties : {};
                        const { color } = getMarkerDisplayData(props, window.currentScoreMode || 'adjusted');
                        applyMarkerGlow(layer, color, false);
                    });
                }
            }, 100);

            // Fit map bounds to loaded ward features
            if (geojsonLayerInstance.getBounds().isValid()) {
                map.fitBounds(geojsonLayerInstance.getBounds());
            }
        })
        .catch(err => {
            showError(err.message);
        });
});
