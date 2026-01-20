# OptionScalp Pro - Ultra Quant Trading System

A professional web-based quantitative trading system for Nifty and Bank Nifty options scalping, featuring TradingView Lightweight Charts and granular Order Flow Footprint visualization.

## Features
- **TradingView Charts:** High-performance, interactive candlestick charts.
- **Order Flow Footprint:** Professional granular view with Bid/Ask bifurcation and imbalance highlighting.
- **Real-time & Replay:** WebSocket-based live monitoring and full historical replay controls (Play, Pause, Step).
- **FastAPI Backend:** Robust data gathering and strategy engine.

## Installation

1. **Clone and Install:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Server:**
   ```bash
   python main.py
   ```

3. **Open Dashboard:**
   Navigate to `http://localhost:8000` in your web browser.

## Project Structure
- `main.py`: FastAPI server and WebSocket hub.
- `data/`: tvDatafeed integration and caching.
- `core/`: Scalping strategies and risk management.
- `templates/`: HTML5 dashboard.
- `static/`: JS (Lightweight Charts) and CSS.

## Usage
- **Go Live:** Fetch real-time Index and ATM Option data.
- **Replay:** Visualize historical setups candle-by-candle on all charts simultaneously.
- **Signals:** Automatic detection of Pullback setups with clear Entry/SL guidance.
