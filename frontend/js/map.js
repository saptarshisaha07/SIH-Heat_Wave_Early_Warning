// Bhubaneswar coordinates
const BHUBANESWAR_COORDS = [20.2961, 85.8245];
const INITIAL_ZOOM = 12;
const GEOJSON_URL = '/api/risk-map';

function showError(message) {
    console.error(message);
    const errorEl = document.getElementById('error-message');
    if (errorEl) {
        errorEl.textContent = 'Error loading ward data: ' + message;
        errorEl.style.display = 'block';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Leaflet map
    const map = L.map('map').setView(BHUBANESWAR_COORDS, INITIAL_ZOOM);

    // 2. Add OpenStreetMap tiles with attribution
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // 3. Add Legend Control
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = function () {
        const div = L.DomUtil.create('div', 'map-legend');
        div.innerHTML = `
            <div class="legend-title">Composite Risk Level</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #28a745;"></span> Normal</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #ffc107;"></span> Caution</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #fd7e14;"></span> Extreme Caution</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #dc3545;"></span> Danger</div>
            <div class="legend-item"><span class="legend-swatch" style="background: #800000;"></span> Extreme Danger</div>
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

            // 5. Render Choropleth markers using circleMarker
            const geojsonLayer = L.geoJSON(data, {
                pointToLayer: (feature, latlng) => {
                    const props = feature.properties || {};
                    const color = props.color || '#28a745';

                    const marker = L.circleMarker(latlng, {
                        radius: 12,
                        fillColor: color,
                        color: '#ffffff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.85
                    });

                    const wardId = props.id || 'Unknown';
                    const wardName = props.name || 'Unknown';
                    const riskCategory = props.risk_category || 'Normal';
                    const riskScore = props.risk_score !== undefined ? props.risk_score : 'N/A';

                    // Bind interactive hover tooltip
                    const tooltipContent = `
                        <div class="ward-tooltip">
                            <strong>${wardId}: ${wardName}</strong><br>
                            Risk: <span style="color: ${color}; font-weight: 700;">${riskCategory}</span> (${riskScore})
                        </div>
                    `;
                    marker.bindTooltip(tooltipContent, {
                        direction: 'top',
                        offset: [0, -10],
                        opacity: 0.95
                    });

                    // Hover effects: highlight marker
                    marker.on('mouseover', function () {
                        this.setRadius(15);
                        this.setStyle({ weight: 3, fillOpacity: 1 });
                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
                            this.bringToFront();
                        }
                    });

                    marker.on('mouseout', function () {
                        this.setRadius(12);
                        this.setStyle({ weight: 2, fillOpacity: 0.85 });
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

            // Fit map bounds to loaded ward features
            if (geojsonLayer.getBounds().isValid()) {
                map.fitBounds(geojsonLayer.getBounds());
            }
        })
        .catch(err => {
            showError(err.message);
        });
});
