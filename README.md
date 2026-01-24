# OptionScalp Cockpit - Backend

This is the backend for the **Modern Options Buyer's Cockpit**. It serves real-time trading data, signals, and analytics via WebSocket following the Cockpit v3.0 Specification.

## 🏗️ System Architecture

The platform is divided into two primary services:

1. **Data Acquisition Hub (Port 8001)**:
   - Manages external data connectivity (MongoDB, Upstox).
   - Handles real-time calculation of Option Greeks, PCR, and Market Buildup.
   - Serves as the WebSocket gateway for the Modern UI.

2. **Strategy Engine (Port 8002)**:
   - Signal generation engine.
   - Evaluates technical strategies in real-time.
   - Triggers signals that are routed back to the Data Hub.

## 🚀 Quick Start

### 1. Configure MongoDB
Ensure MongoDB is running at `localhost:27017` with the `upstox_strategy_db` database and `tick_data` collection containing Upstox Full Feed records.

### 2. Start the Data Hub
```bash
python data_acquisition.py
```

### 3. Start the Strategy Engine
```bash
python engine.py
```

### 4. Connect the Modern UI
Follow the instructions in the [Modern Options Buyer's Cockpit](https://github.com/MaheshUmale/Modern-Options-Buyer-s-Cockpit) repository to start the frontend and connect it to `ws://localhost:8001/ws`.

## ✨ Key Features

- **Cockpit v3.0 Compliance**: Implements the full `MarketState` payload specification.
- **Black-Scholes Greeks**: Real-time calculation of Delta, Gamma, Theta, and Vega.
- **Market Buildup**: Sentiment analysis based on Price and OI relationship.
- **Interactive Replay**: Smooth tick-by-tick replay from MongoDB historical data.

## 🔗 Technical Documentation

- **[Integration Specification](https://github.com/MaheshUmale/Modern-Options-Buyer-s-Cockpit/blob/main/BACKEND_INTEGRATION_SPEC.md)** - Detailed WebSocket data contracts.
