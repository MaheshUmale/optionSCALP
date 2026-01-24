# Data Acquisition Hub (`data_acquisition.py`)

The **Data Acquisition Hub** is the central node of the OptionScalp Pro architecture. It handles external API connectivity (Upstox, Trendlyne), manages the SQLite database, and serves as the WebSocket gateway for the frontend.

## API Contracts & Specifications

### 1. WebSocket Interface (Port 8001)

#### **Inbound Messages (Client -> Hub)**

| Message Type | Field | Type | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `fetch_live` | `index` | `string` | Yes | Target index symbol (e.g., "BANKNIFTY"). |
| `start_replay` | `index` | `string` | Yes | Target index symbol. |
| | `date` | `string` | Yes | Date for replay in "YYYY-MM-DD" format. |
| `run_backtest` | `index` | `string` | Yes | Target index symbol. |
| | `date` | `string` | Yes | Date for backtest in "YYYY-MM-DD" format. |
| `replay_control`| `action` | `string` | Yes | Action to perform: `"play"` or `"pause"`. |

#### **Outbound Messages (Hub -> Client)**

| Message Type | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| `live_data` | `index_symbol` | `string` | The resolved index symbol. |
| | `index_data` | `array[OHLCV]` | Last 300 bars of index data. |
| | `ce_symbol` | `string` | The active Call option symbol. |
| | `ce_data` | `array[OHLCV]` | Last 300 bars of Call data. |
| | `pe_symbol` | `string` | The active Put option symbol. |
| | `pe_data` | `array[OHLCV]` | Last 300 bars of Put data. |
| | `pnl_stats` | `PnLStats` | Current session performance statistics. |
| `replay_info` | `max_idx` | `integer` | Total number of candles in the replay session. |
| | `current_idx` | `integer` | Current progress index. |
| `replay_step` | `market_time` | `string` | Current simulated time (HH:MM:SS). |
| | `index_data` | `array[OHLCV]` | New candles since last step. |
| | `ce_data` | `array[OHLCV]` | New candles since last step. |
| | `pe_data` | `array[OHLCV]` | New candles since last step. |
| | `ce_markers` | `array[Marker]` | Signal markers for the Call chart. |
| | `pe_markers` | `array[Marker]` | Signal markers for the Put chart. |
| | `pnl_stats` | `PnLStats` | Backtest performance statistics. |
| | `pcr_insights` | `PCRInsight` | Calculated PCR for the current interval. |
| `marker_update` | `symbol` | `string` | The symbol the marker belongs to. |
| | `is_ce` / `is_pe` | `boolean` | Flags for chart routing. |
| | `marker` | `Marker` | The visual marker object. |
| | `signal` | `Signal` | The underlying strategy signal details. |
| | `pnl_stats` | `PnLStats` | Updated performance after signal. |

---

### 2. Internal HTTP API (Port 8001)

#### **POST `/api/signal`**
Endpoint used by the **Strategy Engine** to report new trading signals.

**Request Body (Signal Object):**
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `strat_name` | `string` | Yes | Unique identifier of the strategy. |
| `symbol` | `string` | Yes | The trading symbol (e.g., "NSE:BANKNIFTY260123C58800"). |
| `entry_price`| `float` | Yes | The price at which the signal was triggered. |
| `sl` | `float` | No | Stop-loss price level. |
| `target` | `float` | No | Target/Take-profit price level. |
| `reason` | `string` | No | Rationale for the trade. |
| `time` | `integer` | Yes | UNIX timestamp of the signal. |
| `is_pe` | `boolean` | Yes | Whether the signal is for a Put option. |
| `type` | `string` | Yes | Direction of trade (usually `"LONG"`). |

---

### 3. Data Structures (JSON Definitions)

#### **OHLCV Object**
```json
{
  "time": 1705981500,        // integer (UNIX seconds + 19800)
  "open": 58850.5,           // float
  "high": 58870.2,           // float
  "low": 58840.1,            // float
  "close": 58865.0,          // float
  "volume": 1500.0,          // float
  "datetime": "2026-01-23T09:15:00Z" // string (ISO 8601)
}
```

#### **PnLStats Object**
```json
{
  "total_pnl": 1540.25,      // float
  "win_rate": 65.5,          // float (0.0 to 100.0)
  "max_drawdown": 450.0,     // float (absolute value)
  "avg_win": 210.5,          // float
  "avg_loss": -120.0,        // float
  "trade_count": 12          // integer
}
```

#### **Marker Object**
```json
{
  "time": 1705981500,        // integer
  "position": "belowBar",    // string ("aboveBar" | "belowBar")
  "color": "#2196F3",        // string (Hex code)
  "shape": "arrowUp",        // string ("arrowUp" | "arrowDown")
  "text": "TREND_FOLLOWING"  // string
}
```
