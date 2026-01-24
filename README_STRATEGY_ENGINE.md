# Strategy Engine (`engine.py`)

The **Strategy Engine** is a high-performance, stateless processing service dedicated to signal generation and trade management. It encapsulates all trading logic, ensuring that signal generation is identical between Live and Replay modes.

## Functionalities

- **Signal Generation**: Evaluates a library of 21+ strategies (defined in `core/strategies/`) against incoming candle data.
- **Trade Monitoring**: Tracks active trades tick-by-tick against Stop-Loss (SL) and Target levels.
- **Warmup Logic**: Processes the last 300 bars of historical data upon connection to initialize technical indicators (EMAs, VWAP, RSI) and internal strategy state.
- **PnL Analytics**: Calculates real-time PnL, Win Rate, and Drawdown based on premium prices.
- **Validation**: Enforces risk management rules (e.g., 30-point SL for Bank Nifty options).

## Data In

- **JSON OHLCV Payload (via HTTP POST)**:
    - Receives a window of 1-minute or 5-minute candles for the Index, CE (Call), and PE (Put).
    - Includes metadata such as the current timestamp and active trade status.
- **Configuration**:
    - Strategy parameters and risk thresholds from `config.py`.

## Data Out

- **Signal Objects**:
    - Includes `strat_name`, `type` (LONG/SHORT), `entry_price`, `time`, and a plain-English `reason`.
- **Trade Updates**:
    - Real-time exit notifications when SL or Target is breached.
- **Performance Stats**:
    - `total_pnl`, `win_rate`, `avg_win`, `avg_loss`, and `max_drawdown`.

## Data Flow

1. **Ingest**: The Engine receives a 50-bar sliding window of data from the Data Acquisition Hub.
2. **Calculate**: Technical indicators are computed for the entire window to ensure stability.
3. **Evaluate**:
    - Historical candles are checked for signals (Warmup).
    - The latest closed candle is checked for new entry triggers.
    - Active trades are evaluated against the latest "High/Low" or "LTP" for exit conditions.
4. **Return**: The Engine returns a consolidated JSON response containing all active signals and updated PnL statistics to the Hub for broadcasting.
