# OptionScalp Pro - End-to-End Quantitative Trading System

A professional quantitative trading system designed for scalping Nifty and Bank Nifty options using OHLCV data. Rebuilt for high performance using FastAPI, WebSockets, and TradingView Lightweight Charts.

## Key Features
- **Data Gathering:** Real-time and historical data via `tvDatafeed`.
- **Core Logic:** Price Action Pullback strategy for ATM options.
- **Visual Dashboard:** Integrated Index and Option charts.
- **Order Flow Visualization:** Professional-grade numerical footprint chart with Bid/Ask heatmap.
- **Visual Replay:** Candle-by-candle replay system for strategy verification.

## Setup & Run
1. Install dependencies: `pip install -r requirements.txt`
2. Launch server: `python main.py`
3. Open `http://localhost:8000`

## System Architecture
- `/core`: Strategy and risk management logic.
- `/data`: Data gathering and processing layers.
- `/templates` & `/static`: Frontend UI with TradingView charts.
