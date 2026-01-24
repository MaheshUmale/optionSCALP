# UI Server (`ui_server.py`)

The **UI Server** is a lightweight Flask application responsible for serving the frontend assets of the OptionScalp Pro dashboard.

## Functionalities

- **Asset Delivery**: Serves the main HTML structure, CSS styling, and client-side JavaScript.
- **Client Initialization**: Provides the initial landing page that bootstraps the `CommandController` logic in the browser.

## Data In

- **Browser Requests**: Standard HTTP GET requests for:
    - `/` (The main dashboard).
    - `/static/js/*.js` (Chart logic, WebSocket controller).
    - `/static/css/*.css` (The dark-themed professional interface).

## Data Out

- **HTML/JS/CSS**: The browser-ready application bundle.

## Data Flow

1. **Request**: The user navigates to `http://localhost:8000`.
2. **Response**: The UI Server sends `templates/live.html` (the primary dashboard).
3. **Connect**: The browser's client-side JavaScript (`main.js`) detects the host. If it's on port 8000, it automatically establishes a WebSocket connection to the **Data Acquisition Hub** on port 8001.
4. **Render**: The dashboard becomes interactive as it receives the first `live_data` packet from the Hub.
