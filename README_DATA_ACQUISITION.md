# Data Acquisition Hub (`data_acquisition.py`)

The **Data Acquisition Hub** serves as the central nervous system of the OptionScalp Pro application. It manages all external data connections, maintains the local database, and provides a real-time WebSocket interface for the UI.

## Functionalities

- **API Management**: Orchestrates calls to the Upstox API (for OHLCV candles, LTP, and market buildup) and the Trendlyne API (for detailed Open Interest data).
- **PCR Aggregation**: Implements a high-precision Put-Call Ratio (PCR) calculation logic by fetching and summing Open Interest (OI) for 41 strikes (ATM ± 20) per 5-minute interval.
- **Data Persistence**: Manages the `trading_data.db` (SQLite) database, storing OHLCV history, PCR calculations, and trade logs to minimize redundant API calls.
- **WebSocket Gateway**: Serves as the primary WebSocket server (Port 8001), broadcasting live updates, replay steps, and market context to connected clients.
- **Replay Orchestration**: Manages the state machine for "Backtest Replay" mode, incrementally fetching and pushing historical data slices to simulate live trading.

## API Contracts & Data Fields

### WebSocket Commands (Inbound to Hub)

#### `fetch_live`
Initializes a live session for a specific index.
```json
{
  "type": "fetch_live",
  "index": "BANKNIFTY" | "NIFTY"
}
```

#### `start_replay`
Starts a backtest replay for a specific date.
```json
{
  "type": "start_replay",
  "index": "BANKNIFTY" | "NIFTY",
  "date": "YYYY-MM-DD"
}
```

#### `replay_control`
Controls the playback state of the replay engine.
```json
{
  "type": "replay_control",
  "action": "play" | "pause"
}
```

### WebSocket Payloads (Outbound from Hub)

#### `live_data` / `history_data`
Sends full initialization state.
```json
{
  "type": "live_data",
  "index_symbol": "NSE:BANKNIFTY",
  "ce_symbol": "NSE:BANKNIFTY260123C58800",
  "pe_symbol": "NSE:BANKNIFTY260123P58800",
  "index_data": [OHLCV],
  "ce_data": [OHLCV],
  "pe_data": [OHLCV],
  "new_signals": [Signal],
  "pnl_stats": PnLStats,
  "pcr_insights": PCRInsight
}
```

#### `live_update`
Broadcasts real-time price ticks.
```json
{
  "type": "live_update",
  "symbol": "NSE:BANKNIFTY",
  "candle": {
    "time": 1705981500,
    "open": 58850.5,
    "high": 58870.2,
    "low": 58840.1,
    "close": 58865.0,
    "volume": 1500
  }
}
```

### Core Data Structures

#### OHLCV Object
```json
{
  "time": number (UNIX seconds),
  "open": float,
  "high": float,
  "low": float,
  "close": float,
  "volume": float
}
```

#### PCR Insight Object
```json
{
  "pcr": float (Total PE OI / Total CE OI),
  "pcr_change": float,
  "buildup_status": "SHORT COVERING" | "LONG BUILDUP" | "NEUTRAL",
  "trend": "BULLISH" | "BEARISH" | "SIDEWAYS"
}
```

## Data Flow

1. **Request**: A user selects an Index or Date on the UI.
2. **Fetch**: The Hub checks the local DB; if data is missing, it fetches from Upstox or Trendlyne.
3. **Process**: Raw data is normalized (e.g., IST timezone conversion, PCR aggregation).
4. **Sync**: The Hub sends a slice of the data to the **Strategy Engine** to calculate signals/PnL.
5. **Broadcast**: Processed data, signals, and stats are bundled and pushed to the UI via WebSockets.
