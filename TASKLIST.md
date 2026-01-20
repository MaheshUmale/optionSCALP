# OptionScalp Implementation Tasklist

## Phase 1: Infrastructure & Data Gathering
- [x] Create project directory structure
- [x] Set up Python environment and dependencies (`tvDatafeed`, `PyQt6, pyqtgraph`, `plotly`, `pandas`)
- [x] Implement `TvFeed` wrapper for TradingView data fetching
- [x] Implement `DataManager` for caching and retrieving historical OHLCV data for Index and Options

## Phase 2: Core Logic System
- [x] Implement `RiskManager` with specific SL/TP rules (30pts for Bank Nifty, 20pts for Nifty, slippage gaps)
- [x] Implement Strategy 1: Price Action Trend-Following (Pullback Strategy)
    - [x] Trend detection logic
    - [x] Pullback candle anatomy filtering (size, body vs wick)
    - [x] Entry trigger logic (Buy Stop at high + 1)
- [x] Implement Strategy 2: Mean Reversion (Order Flow Trap)
    - [x] Delta proxy calculation from OHLCV
    - [x] Delta divergence detection (Red candle + Positive Delta)
    - [x] VWAP target calculation

## Phase 3: Visualization System
- [x] Implement interactive Candlestick charts using Plotly
- [x] Implement Footprint/Delta visualization (simulated via Delta proxy)
- [x] Integrate signal markers on charts

## Phase 4: UI Development
- [x] Build Streamlit dashboard
- [x] Tab 1: Trade/Market Monitor - Real-time data fetching and signal scanning
- [x] Tab 2: Backtesting UI - historical data analysis and strategy performance evaluation
- [x] Tab 3: Order Flow Analysis - Deep dive into candle data and traps

## Phase 5: Testing & Integration
- [x] Verify data flow from `tvDatafeed` to UI
- [x] Verify strategy signal generation
- [x] End-to-end system verification via UI screenshots
