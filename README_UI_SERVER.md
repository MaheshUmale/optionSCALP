# UI Server (`ui_server.py`)

The **UI Server** is a Flask-based service that provides the web dashboard interface and static assets.

## HTTP Route Registry

| Route | Method | Description | Content Type |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | The main OptionScalp Pro dashboard. | `text/html` |
| `/live_index` | `GET` | Specialized focused Index monitoring view. | `text/html` |
| `/backtest` | `GET` | Historical analysis and performance dashboard. | `text/html` |
| `/chart` | `GET` | Standalone chart view for single symbol focus. | `text/html` |
| `/static/*` | `GET` | Serving JS (main, charts, controller), CSS, and images. | `application/javascript`, `text/css` |

## Data Handling & Bootstrapping

1. **Environment Setup**: The UI Server is primarily a static delivery vehicle. It does not perform market data processing.
2. **WebSocket Handshake**: Upon loading in the browser, `static/js/main.js` performs an automatic cross-origin connection to the **Data Acquisition Hub** on Port 8001.
3. **Redirection Logic**:
   - If `window.location.host` is `localhost:8000`, the WebSocket client targets `ws://localhost:8001/ws`.
4. **Rendering Contract**: The frontend components are built to handle standardized JSON objects (OHLCV, PnLStats, Signals) as defined in the **Data Acquisition Hub Contract**.
