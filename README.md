# OptionScalp Pro - Modular Trading Platform

OptionScalp Pro is a professional-grade trading and backtesting dashboard for Nifty and Bank Nifty options. The system has been refactored into a high-performance, modular 3-tier architecture to ensure scalability and reliability.

## 🏗️ System Architecture

The platform is divided into three independent services:

1. **[Data Acquisition Hub](README_DATA_ACQUISITION.md) (Port 8001)**:
   - Manages external API connectivity (Upstox, Trendlyne).
   - Handles SQLite database persistence for OHLCV, PCR, and Trades.
   - Serves as the real-time WebSocket gateway for the UI.

2. **[Strategy Engine](README_STRATEGY_ENGINE.md) (Port 8002)**:
   - High-performance stateless signal generation engine.
   - Evaluates 21+ technical strategies in real-time.
   - Monitors active trades tick-by-tick for automated exit execution.

3. **[UI Server](README_UI_SERVER.md) (Port 8000)**:
   - Serves the professional dark-themed dashboard and static assets.
   - Handles client-side cross-origin WebSocket initialization.

---

## 🚀 Quick Start

To run the complete platform, start all three services in separate terminals:

### 1. Start the Data Hub
```bash
python data_acquisition.py
```

### 2. Start the Strategy Engine
```bash
python engine.py
```

### 3. Start the UI Server
```bash
python ui_server.py
```

### 4. Access the Dashboard
Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## ✨ Key Features & Fixes

### 📊 Precision PCR Aggregation
- **41 Strikes**: Calculates PCR by summing absolute Open Interest for ATM ± 20 strikes.
- **DB Caching**: All PCR data is stored in `trading_data.db` to prevent redundant API calls.
- **5-Min Buckets**: Data is organized into precise time intervals for trend analysis.

### 💰 Reliable PnL Tracking
- **Option Premiums**: All trade calculations (entries, SL, Targets) are strictly enforced using option premium prices, eliminating scale glitches.
- **Codified Risk**: Standardized 30-point SL for Bank Nifty and 20-point SL for Nifty options.

### 🔄 Advanced Backtest Replay
- **Stable Zoom**: Fixed 80-bar visible window with future-time buffer ensures charts never drift.
- **Incremental Growth**: Replay mode pushes data candle-by-candle for realistic simulation.

---

## 🔗 Technical Documentation

- **[Formal API Contracts (Data Hub)](README_DATA_ACQUISITION.md)** - Exhaustive schemas for WebSocket and HTTP interfaces.
- **[Evaluation Contract (Engine)](README_STRATEGY_ENGINE.md)** - Detailed specs for signal generation requests.
- **[Handshake Details (UI)](README_UI_SERVER.md)** - Frontend data handling and synchronization specs.

---

## 🎨 Professional Design System
- **Institutional Dark Theme**: Optimized for low-eye-strain professional trading.
- **Synchronized Panes**: Crosshair and time-range sync across Index, CE, and PE charts.
- **Action Stream**: Real-time signal log with plain-English rationales and sentiment coloring.

---
**Disclaimer**: This platform is for educational and analysis purposes. Always verify trades with your broker.
