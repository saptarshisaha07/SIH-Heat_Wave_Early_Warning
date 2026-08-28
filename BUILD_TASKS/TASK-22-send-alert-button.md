# Task 22 — "Send Alert" Button (SMS/WhatsApp Simulation UI)

- **Owner**: Frontend Team
- **Status**: PASS
- **What was built**: Implemented the "Send Alert" simulation trigger button and realistic mobile SMS message bubble in the Bhubaneswar Heatwave Early Warning dashboard sidebar. The UI enables municipal operators to simulate automated heatwave alert broadcasts for any selected ward. Built with double-click protection (disabling the button and displaying "Sending..."), clean result replacement to prevent stacking, and comprehensive error handling for network or API failures. All DOM elements are built with `document.createElement` and `textContent` without `innerHTML`, strictly following established architectural patterns.
- **Files changed**:
  - `frontend/js/alerts.js` (new file: implemented `renderAlertButton` and `renderSmsBubble` with button state lifecycle, SMS bubble formatting, and error handling)
  - `frontend/css/style.css` (edited: added styling for `.alert-send-btn`, `.sms-bubble`, `.sms-bubble-meta`, and `.sms-bubble-text`)
  - `frontend/index.html` (edited: added `<script src="js/alerts.js"></script>` after `js/advisory.js` and before `js/app.js`)
  - `frontend/js/app.js` (edited: added "Send Alert" `sidebar-section` container in `renderSidebarData` after "Score Breakdown" and invoked `window.renderAlertButton(data.ward, alertSection)`)
  - `backend/tests/test_e2e_integration.py` (edited: added static asset assertions for `charts.js`, `advisory.js`, `alerts.js`, `style.css`, and mock weather patch)
  - `scratch/test_frontend_alerts.js` (new file: headless unit and integration test suite for Task 22)
  - `BUILD_TASKS/TASK-22-send-alert-button.md` (new file: task build report)
- **Task 21 Endpoint Verification (Step 0)**:
  - **Endpoint inspected**: `POST /api/alerts/simulate` in `backend/app/main.py` and `backend/app/services/alerts.py`.
  - **Real Request Body**:
    ```json
    {
      "ward_id": 1,
      "channel": "sms"
    }
    ```
  - **Real Response Payload**:
    ```json
    {
      "ward_id": 1,
      "ward_name": "Bhubaneswar Zone 01",
      "channel": "sms",
      "status": "simulated",
      "message": "HEAT ALERT: Bhubaneswar Zone 01 is under EXTREME CAUTION risk (Heat Index: 32.4°C). High Heat Stress Warning for Outdoor Workers & Vulnerable Groups. Dial 108/112 for emergencies. - BMC Heat Cell",
      "timestamp": "2026-08-28T19:37:44.776411+00:00"
    }
    ```
  - **Comparison with expected reference spec**: The real implementation fully matched the reference spec (accepted integer `ward_id` and string `channel`, returned `ward_id`, `channel`, `status`, `message`, `timestamp`), and included an additional helpful `ward_name` field.
- **Implementation Approach**:
  1. **Button Lifecycle & Double-Click Protection**:
     - `renderAlertButton(ward, containerElement)` checks for valid ward metadata. If `ward` or `ward.id` is missing, it renders `<p class="placeholder-text">Alert unavailable — ward ID missing.</p>`.
     - When clicked, `button.disabled = true;` and `button.textContent = 'Sending...';` are set immediately before initiating the asynchronous `fetch()` request.
     - On completion (both success and error paths in `finally`), `button.disabled = false;` and `button.textContent = 'Send Alert';` are restored.
  2. **Simulated SMS Bubble (`renderSmsBubble`)**:
     - Prior to appending a new bubble, `containerElement.querySelectorAll('.sms-bubble, .sidebar-error')` are removed so bubbles and errors never stack.
     - Builds `.sms-bubble` container with distinct rounded green-accent styling (`#f0fdf4` background, `4px solid #22c55e` left border).
     - Renders `.sms-bubble-meta` indicating `Simulated ${channel.toUpperCase()} (${status}) — ${timestamp}` to make simulation context explicit.
     - Renders `.sms-bubble-text` containing the exact simulated broadcast text.
  3. **Robust Error Handling**:
     - Handles non-2xx HTTP responses and network connectivity failures.
     - Clears any previous results and displays a `<div class="sidebar-error" role="alert">` with descriptive error messages.
  4. **Sidebar Integration in `app.js`**:
     - Extended `renderSidebarData(data)` to create a labeled `<div class="sidebar-section">` with heading `<h3>Send Alert</h3>` immediately following the "Score Breakdown" section.
     - Passes `data.ward` (containing `data.ward.id`) to `window.renderAlertButton`.
     - Switching wards triggers `renderSidebarLoading`/`renderSidebarData`, which tears down the entire `#ward-details` container and rebuilds fresh state naturally.
- **How to verify**:
  1. **Run full backend unit test suite**:
     ```bash
     cd backend && python -m unittest discover -s tests -p "test_*.py"
     ```
     *Expect*: All 51 tests pass (`OK`).
  2. **Run frontend headless test suite**:
     ```bash
     node scratch/test_frontend_alerts.js
     ```
     *Expect*: All 8 tests pass (button rendering, click handling, SMS bubble creation, bubble replacement, error state, sidebar integration, script ordering).
  3. **Interactive Browser Verification**:
     - Start FastAPI backend: `cd backend && python -m uvicorn app.main:app --port 8000`
     - Open `http://127.0.0.1:8000/` (or via frontend dev server).
     - Click on ward marker `BBSR-01`:
       - Verify "Send Alert" section appears at the bottom of the sidebar below "Score Breakdown".
       - Click "Send Alert" button: verify button switches to "Sending...", then returns to "Send Alert", displaying a green simulated SMS bubble with the real alert message and timestamp.
       - Click "Send Alert" again: verify the bubble updates and does not duplicate or stack.
     - Switch to `BBSR-02` and back to `BBSR-01`:
       - Verify sidebar rebuilds cleanly without leftover alert bubbles or console errors.
- **Blockers or known limitations**: None.
