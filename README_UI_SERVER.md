# UI Server (`ui_server.py`)

The **UI Server** is a lightweight Flask application responsible for serving the frontend assets of the OptionScalp Pro dashboard.

## Interaction Details & Data Handling

### Client-Side Architecture

The UI is driven by `static/js/main.js` which manages a `CommandController`. This controller is responsible for:
- **WebSocket Handshake**: Connecting to the Data Acquisition Hub (Port 8001).
- **State Management**: Keeping track of current Index (BANKNIFTY/NIFTY) and Mode (LIVE/REPLAY).
- **Chart Orchestration**: Feeding data into `ChartManager` (Lightweight Charts) for rendering.

### Frontend Data Expectations

The UI expects standardized payloads from the Hub to render components:

#### 1. Market Context Rendering
Expects a `pcr_insights` object to update the "Market Context" sidebar.
- **Trend Label**: Updates `market-trend` element.
- **PCR Value**: Updates `pcr-value` element.
- **Buildup Badge**: Dynamic color coding based on `buildup_status`.

#### 2. Action Stream
Expects a `new_signals` array. Each signal is rendered as a "Stream Item":
- **Bullish**: Green border/text (if sentiment is BULLISH or symbol contains 'CE').
- **Bearish**: Red border/text (if sentiment is BEARISH or symbol contains 'PE').
- **Tooltip**: Displays the `reason` field on hover.

#### 3. Chart Synchronization
The `ChartManager` handles synchronization across three panes (Index, CE, PE):
- **Crosshair Sync**: Moving mouse on one chart moves it on others.
- **Time Range Sync**: Zooming/panning is locked across all three charts using an `isSyncing` guard.
- **Replay Growth**: For `replay_step`, the chart uses `update` rather than `setData` to provide a smooth "live-growing" effect.

## Data Flow

1. **Request**: User navigates to `http://localhost:8000`.
2. **Bootstrap**: `ui_server.py` delivers the HTML/JS bundle.
3. **Cross-Origin Connect**: `main.js` detects the environment and connects to the Hub on port 8001.
4. **Interactive State**: The Hub pushes `live_data`, and the UI populates charts and stats panels.
