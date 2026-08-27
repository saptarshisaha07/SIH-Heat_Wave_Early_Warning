// Bhubaneswar coordinates
const BHUBANESWAR_COORDS = [20.2961, 85.8245];
const INITIAL_ZOOM = 12;
const GEOJSON_URL = '/backend/data/wards.geojson';

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

    // 3. Fetch GeoJSON ward data
    fetch(GEOJSON_URL)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch ${GEOJSON_URL} (Status: ${response.status} ${response.statusText})`);
            }
            return response.json();
        })
        .then(data => {
            // 4. Validate GeoJSON FeatureCollection
            if (!data || data.type !== 'FeatureCollection' || !Array.isArray(data.features)) {
                throw new Error('Invalid GeoJSON format: Expected a FeatureCollection with a features array.');
            }

            // 5. Confirm feature count is between 8 and 15
            const featureCount = data.features.length;
            if (featureCount < 8 || featureCount > 15) {
                throw new Error(`Invalid feature count: Expected between 8 and 15 features, but got ${featureCount}.`);
            }

            // 6. Add GeoJSON to the map
            const geojsonLayer = L.geoJSON(data, {
                onEachFeature: (feature, layer) => {
                    const wardId = feature.properties && feature.properties.id ? feature.properties.id : 'Unknown';
                    const wardName = feature.properties && feature.properties.name ? feature.properties.name : 'Unknown';

                    // 7. Bind popup showing ward ID and name
                    const popupContent = `<strong>${wardId}</strong><br>${wardName}`;
                    layer.bindPopup(popupContent);

                    // 8. Register click handler logging exact ward ID and notifying app
                    layer.on('click', () => {
                        console.log(`Clicked ward: ${wardId}`);
                        if (typeof window.handleWardMarkerClick === 'function') {
                            window.handleWardMarkerClick(wardId);
                        }
                    });
                }
            }).addTo(map);

            // 9. Fit map bounds to loaded ward features
            if (geojsonLayer.getBounds().isValid()) {
                map.fitBounds(geojsonLayer.getBounds());
            }
        })
        .catch(err => {
            // 10. Show visible human-readable error on page
            showError(err.message);
        });
});
