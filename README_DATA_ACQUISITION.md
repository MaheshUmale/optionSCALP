# Data Acquisition Hub (`data_acquisition.py`)

The **Data Acquisition Hub** serves as the central nervous system of the OptionScalp Pro application. It manages all external data connections, maintains the local database, and provides a real-time WebSocket interface for the UI.

## Functionalities

- **API Management**: Orchestrates calls to the Upstox API (for OHLCV candles, LTP, and market buildup) and the Trendlyne API (for detailed Open Interest data).
- **PCR Aggregation**: Implements a high-precision Put-Call Ratio (PCR) calculation logic by fetching and summing Open Interest (OI) for 41 strikes (ATM ± 20) per 5-minute interval.
- **Data Persistence**: Manages the `trading_data.db` (SQLite) database, storing OHLCV history, PCR calculations, and trade logs to minimize redundant API calls.
- **WebSocket Gateway**: Serves as the primary WebSocket server (Port 8001), broadcasting live updates, replay steps, and market context to connected clients.
- **Replay Orchestration**: Manages the state machine for "Backtest Replay" mode, incrementally fetching and pushing historical data slices to simulate live trading.

## Data In

- **Upstox API**:
    - Historical 1-minute and 5-minute OHLCV candles for Indices and Options.
    - Live WebSocket feed (`marketFF` and `indexFF`) for tick-by-tick updates.
- **Trendlyne API**:
    - Per-strike buildup and OI data for Nifty and Bank Nifty option chains.
- **UI WebSocket Commands**:
    - `fetch_live`: Requests initialization data for a specific index.
    - `start_replay`: Triggers historical data simulation for a specific date.
    - `replay_control`: Play/Pause signals for the replay loop.

## Data Out

- **WebSocket Payloads**:
    - `live_data`: Initial dashboard state (candles, markers, PnL stats).
    - `live_update`: Real-time price ticks and candle closures.
    - `replay_step`: Incremental data slices for backtesting.
    - `pcr_update`: Fresh PCR insights and trend analysis.
- **SQLite DB**:
    - Persisted OHLCV bars in the `ohlcv` table.
    - Calculated PCR history in the `pcr_data` table.
    - Live and historical trade records in the `trades` table.

## Data Flow

1. **Request**: A user selects an Index or Date on the UI.
2. **Fetch**: The Hub checks the local DB; if data is missing, it fetches from Upstox or Trendlyne.
3. **Process**: Raw data is normalized (e.g., IST timezone conversion, PCR aggregation).
4. **Sync**: The Hub sends a slice of the data to the **Strategy Engine** to calculate signals/PnL.
5. **Broadcast**: Processed data, signals, and stats are bundled and pushed to the UI via WebSockets.
