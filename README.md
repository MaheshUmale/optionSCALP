# OptionScalp Pro - Ultra Quant Trading System

A professional web-based quantitative trading system for Nifty and Bank Nifty options scalping, featuring TradingView Lightweight Charts and a specialized Delta Volume Strategy for identifying high-probability buying opportunities.

## Features
- **TradingView Charts:** High-performance, interactive candlestick charts using the `lightweight-charts` library (v4.2.3).
- **Delta Volume Strategy:** Advanced order-flow logic that identifies "Short Covering" (Sellers Exiting) by analyzing Net Delta Volume, Open Interest (OI) changes, and price momentum from Trendlyne 5-minute buildup data.
- **Real-time & Replay:** Dual-mode interface. Live mode provides real-time data streaming via WebSockets, while Replay mode allows for candle-by-candle historical playback.
- **Automated Symbol Mapping:** Calculates nearest NSE expiry and dynamically maps Index trends to the most relevant ATM/OTM Call and Put options.
- **Trendlyne Integration:** Asynchronous data retrieval from Trendlyne for 5-minute buildup clusters (ATM, ITM, and OTM strikes) to detect professional order flow behavior.
- **FastAPI Backend:** High-concurrency Python backend using FastAPI, WebSockets, and `httpx` for non-blocking data acquisition.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd optionSCALP
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *Note: Includes a direct GitHub install for the latest `tvDatafeed` features.*

## How to Run

### Windows (Command Prompt)
```cmd
set PYTHONPATH=.;%PYTHONPATH%
python main.py
```

### Windows (PowerShell)
```powershell
$env:PYTHONPATH=".;" + $env:PYTHONPATH
python main.py
```

### Linux / macOS
```bash
export PYTHONPATH=$PYTHONPATH:.
python main.py
```

After running, open your browser and navigate to: **`http://localhost:8000`**

## Usage Guide
- **Go Live:** Connects to TradingView and fetches real-time Index and ATM Option data. The system automatically refreshes Trendlyne Delta signals at the start of every new candle.
- **Replay Mode:** Accessible via `/replay`. Allows users to load historical data and step through it to verify strategy signals and visualize market pivots.
- **Delta Volume Signals:** The system identifies bullish/bearish opportunities when sellers are "trapped" (Price rising/falling + Falling OI + Volume Spike). These are displayed in the real-time signal list.
- **Visual Markers:** Entry setups and strategy signals are plotted directly on the charts as "BUY" markers for quick execution reference.

## Backtest Result: Jan 21, 2026
- **Symbol:** BANKNIFTY (Bullish Signal)
- **Setup:** Delta Volume Short Covering detected on Call Strikes.
- **Signal:** Net Delta Positive | Call OI Decreasing | Price Momentum Up.
- **Result:** High-probability momentum breakout confirmed in Replay.

## Project Structure
- `main.py`: FastAPI server and WebSocket manager.
- `core/`: Scalping logic and risk management.
- `data/`: TradingView data feed and caching.
- `static/`: Frontend assets (script.js, style.css).
- `templates/`: HTML5 dashboard.
