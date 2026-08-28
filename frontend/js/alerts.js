/**
 * Alerts simulation module for Bhubaneswar Heatwave Early Warning System.
 * Provides on-demand SMS / WhatsApp heat warning simulation triggers with
 * realistic mobile message bubble UI, double-click protection, and error handling.
 */

/**
 * Creates and renders a simulated SMS-style message bubble.
 * Uses textContent and createElement exclusively to prevent XSS vulnerabilities.
 *
 * @param {Object} alertData - Payload returned from POST /api/alerts/simulate
 * @param {HTMLElement} containerElement - Parent DOM container element
 */
function renderSmsBubble(alertData, containerElement) {
    if (!alertData || !containerElement) {
        return;
    }

    // 1. Clear any prior alert bubbles or error notices in this container so results do not stack
    const existingResults = containerElement.querySelectorAll('.sms-bubble, .sidebar-error');
    existingResults.forEach(el => el.remove());

    // 2. Build bubble container
    const bubble = document.createElement('div');
    bubble.className = 'sms-bubble';

    // 3. Channel + status + timestamp metadata header
    const metaDiv = document.createElement('div');
    metaDiv.className = 'sms-bubble-meta';

    const channelStr = alertData.channel ? String(alertData.channel).toUpperCase() : 'SMS';
    const statusStr = alertData.status ? String(alertData.status) : 'simulated';
    const timestampStr = alertData.timestamp ? String(alertData.timestamp) : new Date().toISOString();

    metaDiv.textContent = `Simulated ${channelStr} (${statusStr}) — ${timestampStr}`;
    bubble.appendChild(metaDiv);

    // 4. Simulated message content body
    const bodyP = document.createElement('div');
    bodyP.className = 'sms-bubble-text';
    bodyP.textContent = alertData.message || 'No alert message content available.';
    bubble.appendChild(bodyP);

    // 5. Append to container
    containerElement.appendChild(bubble);
}

/**
 * Renders the "Send Alert" simulation trigger button into the specified sidebar section container.
 *
 * @param {Object} ward - Ward metadata object containing `id` (e.g. data.ward)
 * @param {HTMLElement} containerElement - DOM element container where the button and alert bubble should live
 */
function renderAlertButton(ward, containerElement) {
    if (!containerElement) {
        return;
    }

    // 1. If ward or ward.id is missing, show placeholder text and return early
    if (!ward || ward.id === undefined || ward.id === null) {
        const placeholder = document.createElement('p');
        placeholder.className = 'placeholder-text';
        placeholder.textContent = 'Alert unavailable — ward ID missing.';
        containerElement.appendChild(placeholder);
        return;
    }

    // 2. Create the Send Alert button
    const button = document.createElement('button');
    button.className = 'alert-send-btn';
    button.textContent = 'Send Alert';
    button.type = 'button';
    containerElement.appendChild(button);

    // 3. Attach click handler with race-condition / double-click protection
    button.addEventListener('click', async () => {
        // Disable button & indicate active request
        button.disabled = true;
        button.textContent = 'Sending...';

        // Clear any previous bubble or error in container
        const existingResults = containerElement.querySelectorAll('.sms-bubble, .sidebar-error');
        existingResults.forEach(el => el.remove());

        const baseUrl = window.API_BASE_URL || '';
        const url = `${baseUrl}/api/alerts/simulate`;

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ward_id: Number(ward.id),
                    channel: 'sms'
                })
            });

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
                throw new Error(`Alert simulation failed (Status ${response.status}): ${errorDetail}`);
            }

            const data = await response.json();
            renderSmsBubble(data, containerElement);
        } catch (error) {
            // Remove previous error/bubble if any
            const prevResults = containerElement.querySelectorAll('.sms-bubble, .sidebar-error');
            prevResults.forEach(el => el.remove());

            const errorDiv = document.createElement('div');
            errorDiv.className = 'sidebar-error';
            errorDiv.setAttribute('role', 'alert');
            errorDiv.textContent = error.message || 'Failed to simulate alert. Please try again.';
            containerElement.appendChild(errorDiv);
        } finally {
            // Re-enable button
            button.disabled = false;
            button.textContent = 'Send Alert';
        }
    });
}

// Expose globally on window for app.js
window.renderAlertButton = renderAlertButton;
