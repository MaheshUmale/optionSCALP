# OptionScalp

A professional-grade quantitative trading system for Nifty and Bank Nifty options scalping, built with PyQt6 and TradingView data.

## Features
- **Data Gathering:** Real-time Index and ATM Option data using `tvDatafeed`.
- **Core Logic:** Pullback and Mean Reversion strategies with strict risk management (30-point SL for Bank Nifty).
- **Advanced Visualization:** High-performance Candlestick and Footprint (Order Flow) charts with price clustering.
- **Pro UI:** Desktop dashboard with live auto-refresh, signal tracking, and trade details.
- **Backtesting:** Integrated tab for historical strategy evaluation.

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
   *Note: `tvDatafeed` is installed directly from GitHub to ensure the latest live data features.*

3. **System Requirements:**
   - Python 3.8+
   - A desktop environment (Windows/macOS/Linux with X11) for the PyQt6 GUI.

## How to Run

### Windows (Command Prompt)
```cmd
set PYTHONPATH=%PYTHONPATH%;.
python main.py
```

### Windows (PowerShell)
```powershell
$env:PYTHONPATH += ";."
python main.py
```

### Linux / macOS (Terminal)
```bash
export PYTHONPATH=$PYTHONPATH:.
python main.py
```

## Usage Instructions
1. **Refresh Data:** Click the "Refresh Market Data" button to fetch the latest bars.
2. **Auto-Refresh:** Toggle the "Auto-Refresh" button to enable live monitoring (refreshes every 1 minute).
3. **Footprint View:** Switch to the "Footprint Analysis" tab to see volume clusters and buy/sell imbalances.
4. **Signals:** Active setups appear in the right-hand panel with entry, stop loss, and target prices.
5. **Chart Navigation:**
   - Use the mouse wheel to zoom.
   - Click and drag to pan.
   - Signals are marked with Blue (Entry) and Red (SL) lines.

## Strategies
- **Trend-Following:** Identifies index trend on 15m timeframe and waits for a 5m pullback on ATM Call/Put options.
- **Mean Reversion:** Detects Delta Divergence and "Traps" at day extremes to target the VWAP.

## Disclaimer
This system is for educational and research purposes only. Trading options involves significant risk. Always test thoroughly in a simulated environment before using real capital.
