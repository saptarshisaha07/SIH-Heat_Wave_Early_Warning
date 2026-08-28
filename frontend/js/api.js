/**
 * API client for Bhubaneswar Heatwave Early Warning System.
 * Fetches live weather, thermal index, and composite risk data for wards.
 */

/**
 * Maps a ward identifier (e.g., 'BBSR-01', '1', or 1) to the numeric API ID.
 * GeoJSON features use IDs formatted as 'BBSR-01' through 'BBSR-10',
 * while the backend GET /api/wards/{id} endpoint expects numeric database IDs (1 through 10).
 *
 * @param {string|number} wardId - Ward identifier from GeoJSON or database
 * @returns {number} Numeric database ID
 */
function resolveWardApiId(wardId) {
    if (typeof wardId === 'number' && Number.isInteger(wardId) && wardId > 0) {
        return wardId;
    }
    if (typeof wardId === 'string') {
        const trimmed = wardId.trim();
        const match = trimmed.match(/^(?:BBSR-)?(\d+)$/i);
        if (match) {
            const parsed = parseInt(match[1], 10);
            if (!isNaN(parsed) && parsed > 0) {
                return parsed;
            }
        }
    }
    throw new Error(`Invalid ward ID: "${wardId}". Expected numeric ID or format "BBSR-XX".`);
}

/**
 * Fetches real-time weather, thermal indices, and risk assessment for a ward.
 *
 * @param {string|number} wardId - The ward identifier (e.g. 'BBSR-01' or 1)
 * @returns {Promise<Object>} The parsed ward risk slice payload
 */
async function getWardDetails(wardId) {
    const apiId = resolveWardApiId(wardId);
    const baseUrl = window.API_BASE_URL || '';
    const url = `${baseUrl}/api/wards/${apiId}`;

    const response = await fetch(url);
    if (!response.ok) {
        let errorDetail = response.statusText;
        try {
            const errorJson = await response.json();
            if (errorJson && errorJson.detail) {
                errorDetail = errorJson.detail;
            }
        } catch (_) {
            // Fallback to response.statusText if body is not JSON
        }
        throw new Error(`API request failed with status ${response.status}: ${errorDetail}`);
    }

    const data = await response.json();
    return data;
}

// Expose globally on window for app.js
window.getWardDetails = getWardDetails;
window.resolveWardApiId = resolveWardApiId;
