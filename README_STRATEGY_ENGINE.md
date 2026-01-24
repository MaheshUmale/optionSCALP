# Strategy Engine (`engine.py`)

The **Strategy Engine** is a stateless processing unit that receives market data from the Hub and returns strategy evaluations and performance analytics.

## API Contracts & Specifications

### 1. HTTP Interface (Port 8002)

#### **POST `/evaluate`**
The primary entry point for market data analysis.

**Request Body:**
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `index_sym` | `string` | Yes | Root index symbol (e.g., "NSE:BANKNIFTY"). |
| `ce_sym` | `string` | Yes | Call option symbol being monitored. |
| `pe_sym` | `string` | Yes | Put option symbol being monitored. |
| `index_data`| `array[OHLCV]` | Yes | Time-series data for the underlying index. |
| `ce_data` | `array[OHLCV]` | Yes | Time-series data for the Call option. |
| `pe_data` | `array[OHLCV]` | Yes | Time-series data for the Put option. |
| `pcr_insights`| `PCRInsight` | Yes | Current PCR and market sentiment data. |
| `candle_time`| `integer` | Yes | UNIX timestamp of the current bar being evaluated. |

**Response Body:**
```json
{
  "status": "ok"
}
```
*Note: Signals generated during evaluation are reported asynchronously to the Hub via its `/api/signal` endpoint.*

---

### 2. Outbound HTTP Calls (Engine -> Hub)

#### **POST `http://localhost:8001/api/signal`**
The Engine emits this call whenever a strategy condition is met.

| Field | Type | Description |
| :--- | :--- | :--- |
| `strat_name` | `string` | Name of the triggering strategy. |
| `symbol` | `string` | Symbol to trade. |
| `entry_price`| `float` | Latest closing price of the option. |
| `sl` | `float` | Calculated stop-loss. |
| `target` | `float` | Calculated target profit. |
| `reason` | `string` | Detailed rationale for the entry. |
| `time` | `integer` | Candle time in UNIX seconds. |
| `is_pe` | `boolean` | `true` for Put signals, `false` for Call. |
| `type` | `string` | Trade direction (`"LONG"`). |

---

### 3. Data Structures (JSON Definitions)

#### **PCRInsight Object**
```json
{
  "pcr": 1.05,               // float
  "pcr_change": 0.02,        // float (optional)
  "buildup_status": "LONG BUILDUP", // string
  "trend": "BULLISH"         // string ("BULLISH" | "BEARISH" | "SIDEWAYS")
}
```

#### **Signal Object**
Refer to the definition in `README_DATA_ACQUISITION.md`.

## Core Logic & Functionalities

- **Statelessness**: The engine does not store trade state; it receives the required window of history (typically 50-100 bars) in every request.
- **Unified Strategy Interface**: Supports 21+ individual strategies inheriting from `BaseStrategy`.
- **EMA/Filter Logic**: Applies standardized filters (e.g., 9-EMA and 14-EMA slope checks) before emitting signals.
