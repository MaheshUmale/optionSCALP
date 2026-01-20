# OptionScalp Pro - Ultra Quant Trading System

A professional web-based quantitative trading system for Nifty and Bank Nifty options scalping, featuring TradingView Lightweight Charts and a granular Order Flow Footprint visualization.

## Features
- **TradingView Charts:** High-performance, interactive candlestick charts using the `lightweight-charts` library.
- **Order Flow Footprint:** Professional "Split-Cell" layout (Sellers on Left, Buyers on Right) with heatmap intensity and imbalance highlighting.
- **Real-time & Replay:** WebSocket-based live monitoring and full historical replay controls (Play, Pause, Step).
- **Automated Symbol Mapping:** Calculates nearest NSE expiry (Tuesday/Jan 2026 dates) and maps Index trends to ATM Call/Put options.
- **FastAPI Backend:** Robust Python backend for data gathering (via `tvDatafeed`) and scalping strategy execution.

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
- **Go Live:** Connects to TradingView and fetches real-time Index and ATM Option data based on the current trend.
- **Replay Control:** Switch to the "Replay Control" tab to visualize historical data candle-by-candle. This is perfect for verifying setups.
- **Order Flow:** The side panel provides a real-time Footprint view of the last candle, showing volume distribution and aggressive imbalances.
- **Signals:** Strategy 1 (Pullback) signals are automatically plotted as markers on the chart and listed in the signal panel.

## Backtest Result: Jan 20, 2026
- **Symbol:** BANKNIFTY260120P59400 (Bearish Index Trend)
- **Setup:** Valid Small Bearish Pullback Candle detected.
- **Signal:** BUY Above **295.95** | SL: **255.90** | Target: **325.95+**

## Project Structure
- `main.py`: FastAPI server and WebSocket manager.
- `core/`: Scalping logic and risk management.
- `data/`: TradingView data feed and caching.
- `static/`: Frontend assets (script.js, style.css).
- `templates/`: HTML5 dashboard.
