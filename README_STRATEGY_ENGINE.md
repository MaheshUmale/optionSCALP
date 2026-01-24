# Strategy Engine (`engine.py`)

The **Strategy Engine** is a high-performance, stateless processing service dedicated to signal generation and trade management. It encapsulates all trading logic, ensuring that signal generation is identical between Live and Replay modes.

## API Contracts & Data Fields

### `/evaluate` (HTTP POST)

The primary endpoint for processing market data and receiving trading decisions.

#### Request Body
```json
{
  "index_data": [OHLCV],
  "ce_data": [OHLCV],
  "pe_data": [OHLCV],
  "current_idx": number,
  "is_index_driven": boolean,
  "active_trades": [
    {
      "symbol": string,
      "entry_price": float,
      "status": "OPEN",
      "trade_type": "LONG" | "SHORT"
    }
  ]
}
```

#### Response Body
```json
{
  "signals": [Signal],
  "pnl_stats": PnLStats,
  "exit_signals": [
    {
      "symbol": string,
      "exit_price": float,
      "reason": "SL_BREACH" | "TARGET_BREACH" | "EOD_SQUARE_OFF"
    }
  ]
}
```

### Core Data Structures

#### Signal Object
```json
{
  "strat_name": string,
  "type": "LONG" | "SHORT",
  "symbol": string (NSE:BANKNIFTY...C...),
  "entry_price": float,
  "time": number (UNIX seconds),
  "reason": string (Plain English rationale),
  "sentiment": "BULLISH" | "BEARISH",
  "setup": object (Strategy-specific indicators)
}
```

#### PnLStats Object
```json
{
  "total_pnl": float,
  "win_rate": float (0-100),
  "max_drawdown": float,
  "avg_win": float,
  "avg_loss": float,
  "trade_count": number
}
```

## Functionalities

- **Signal Generation**: Evaluates a library of 21+ strategies against incoming candle data.
- **Trade Monitoring**: Tracks active trades tick-by-tick against Stop-Loss (SL) and Target levels.
- **Warmup Logic**: Processes the last 300 bars of historical data upon connection to initialize technical indicators (EMAs, VWAP, RSI).
- **PnL Analytics**: Calculates real-time PnL, Win Rate, and Drawdown based on premium prices.

## Data Flow

1. **Ingest**: The Engine receives a 50-bar sliding window of data from the Data Acquisition Hub.
2. **Calculate**: Technical indicators are computed for the entire window to ensure stability.
3. **Evaluate**: Latest candles are checked for signals and active trades are checked for exits.
4. **Return**: Consolidated results are sent back to the Hub.
