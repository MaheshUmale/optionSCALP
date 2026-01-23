/**
 * OptionScalp Pro - Main Application
 */

import { CONFIG } from './config.js';
import { WebSocketManager } from './websocket.js';
import { ChartManager } from './charts/manager.js';
import { SignalsWidget } from './widgets/signals.js';
import { PnLWidget } from './widgets/pnl.js';
import { MarketOverviewWidget } from './widgets/market.js';
import { StrategyWidget } from './widgets/strategies.js';
import { PositionsWidget } from './widgets/positions.js';

class OptionScalpDashboard {
    constructor() {
        // Initialize managers
        this.ws = new WebSocketManager();
        this.chartManager = new ChartManager();

        // Initialize widgets
        this.signalsWidget = new SignalsWidget('signals-panel');
        this.pnlWidget = new PnLWidget();
        this.marketWidget = new MarketOverviewWidget();
        this.strategyWidget = new StrategyWidget('strategy-performance');
        this.positionsWidget = new PositionsWidget('positions-list');

        // State
        this.currentIndex = 'BANKNIFTY';
        this.symbols = {
            index: '',
            ce: '',
            pe: ''
        };

        this.setupEventListeners();
        this.setupWebSocket();
    }

    setupEventListeners() {
        // Go Live button
        document.getElementById('btn-live')?.addEventListener('click', () => {
            this.fetchLive();
        });

        // Index selector
        document.getElementById('index-select')?.addEventListener('change', (e) => {
            this.currentIndex = e.target.value;
        });

        // Tab switching
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Connection status indicator
        this.ws.onConnectionChange = (connected) => {
            this.updateConnectionStatus(connected);
        };
    }

    setupWebSocket() {
        // Handle different message types
        this.ws.on('live_data', (data) => this.handleLiveData(data));
        this.ws.on('live_update', (data) => this.handleLiveUpdate(data));
        this.ws.on('pcr_update', (data) => this.handlePCRUpdate(data));
        this.ws.on('replay_step', (data) => this.handleLiveData(data));
        this.ws.on('backtest_results', (data) => this.handleBacktestResults(data));
        this.ws.on('marker_update', (data) => this.handleMarkerUpdate(data));
        this.ws.on('reset_ui', () => this.resetUI());
        this.ws.on('error', (data) => this.handleError(data));

        // Connect
        this.ws.connect();
    }

    fetchLive() {
        this.ws.send({
            type: 'fetch_live',
            index: this.currentIndex
        });
    }

    handleLiveData(data) {
        // Update symbols
        if (data.index_symbol) this.symbols.index = data.index_symbol;
        if (data.ce_symbol) this.symbols.ce = data.ce_symbol;
        if (data.pe_symbol) this.symbols.pe = data.pe_symbol;

        // Update chart data
        if (data.index_data) {
            this.chartManager.updateChartData('index', data.index_data);
            this.chartManager.fitContent('index');
            this.updateChartLabels('index', this.symbols.index, data.index_data);
        }

        if (data.ce_data) {
            this.chartManager.updateChartData('ce', data.ce_data);
            this.chartManager.fitContent('ce');
            this.updateChartLabels('ce', this.symbols.ce, data.ce_data);
        }

        if (data.pe_data) {
            this.chartManager.updateChartData('pe', data.pe_data);
            this.chartManager.fitContent('pe');
            this.updateChartLabels('pe', this.symbols.pe, data.pe_data);
        }

        // Update markers
        if (data.ce_markers) {
            this.chartManager.setMarkers('ce', data.ce_markers);
        }

        if (data.pe_markers) {
            this.chartManager.setMarkers('pe', data.pe_markers);
        }

        // Update market overview
        if (data.trend) {
            this.marketWidget.updateTrend(data.trend);
        }

        if (data.pcr_insights) {
            this.marketWidget.updatePCR(data.pcr_insights);
        }

        // Update PnL stats
        if (data.pnl_stats) {
            this.pnlWidget.update(data.pnl_stats);
        }

        // Update signals
        if (data.new_signals && Array.isArray(data.new_signals)) {
            data.new_signals.forEach(signal => {
                this.signalsWidget.addSignal(signal);
            });
        }

        // Update strategy report
        if (data.strategy_report) {
            this.strategyWidget.update(data.strategy_report);
        }

        // Update active positions
        if (data.active_positions) {
            this.positionsWidget.update(data.active_positions);
        }

        // Update popout links
        this.updatePopoutLinks();

        // Update status
        document.getElementById('status-text').textContent = 'Connected';
    }

    handleLiveUpdate(data) {
        const candle = data.candle;
        if (!candle) return;

        // Update appropriate chart
        if (data.is_index) {
            this.chartManager.updateLiveCandle('index', candle);
            this.updatePrice('index', candle.close);
            this.marketWidget.updateIndexPrice(candle.close);
        } else if (data.is_ce) {
            this.chartManager.updateLiveCandle('ce', candle);
            this.updatePrice('ce', candle.close);
        } else if (data.is_pe) {
            this.chartManager.updateLiveCandle('pe', candle);
            this.updatePrice('pe', candle.close);
        }
    }

    handlePCRUpdate(data) {
        if (data.pcr_insights) {
            this.marketWidget.updatePCR(data.pcr_insights);
        }
        if (data.trend) {
            this.marketWidget.updateTrend(data.trend);
        }
    }

    handleMarkerUpdate(data) {
        if (data.is_ce) {
            this.chartManager.addMarker('ce', data.marker);
        }
        if (data.is_pe) {
            this.chartManager.addMarker('pe', data.marker);
        }
        if (data.signal) {
            this.signalsWidget.addSignal(data.signal);
        }
    }

    handleBacktestResults(data) {
        this.handleLiveData(data);
    }

    handleError(data) {
        console.error('Server error:', data.message);
        alert(`Error: ${data.message}`);
    }

    resetUI() {
        this.chartManager.clearAllCharts();
        this.signalsWidget.clear();
        this.pnlWidget.reset();
        this.marketWidget.reset();
        this.marketWidget.reset();
        this.strategyWidget.showEmpty();
        this.positionsWidget.update([]);
    }

    updateChartLabels(chartId, symbol, data) {
        const symbolEl = document.getElementById(`${chartId}-symbol`);
        if (symbolEl) {
            symbolEl.textContent = symbol.replace('NSE:', '');
        }

        if (data && data.length > 0) {
            const lastCandle = data[data.length - 1];
            this.updatePrice(chartId, lastCandle.close);
        }
    }

    updatePrice(chartId, price) {
        const priceEl = document.getElementById(`${chartId}-price-display`);
        if (priceEl) {
            priceEl.textContent = `₹${price.toFixed(2)}`;
        }
    }

    updatePopoutLinks() {
        // Update index popout
        const indexPopout = document.getElementById('index-popout-btn');
        if (indexPopout && this.symbols.index) {
            indexPopout.href = `/chart?symbol=${this.symbols.index}`;
        }

        // Update CE popout
        const cePopout = document.getElementById('ce-popout-btn');
        if (cePopout && this.symbols.ce) {
            cePopout.href = `/chart?symbol=${this.symbols.ce}`;
        }

        // Update PE popout
        const pePopout = document.getElementById('pe-popout-btn');
        if (pePopout && this.symbols.pe) {
            pePopout.href = `/chart?symbol=${this.symbols.pe}`;
        }
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.panel-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.panel-tab-content').forEach(content => {
            content.style.display = 'none';
        });

        const activeContent = document.getElementById(`${tabName}-tab`);
        if (activeContent) {
            activeContent.style.display = 'block';
        }
    }

    updateConnectionStatus(connected) {
        const statusText = document.getElementById('status-text');
        const statusDot = document.querySelector('.status-dot');

        if (connected) {
            statusText.textContent = 'Connected';
            statusDot.style.background = 'var(--success)';
        } else {
            statusText.textContent = 'Disconnected';
            statusDot.style.background = 'var(--danger)';
        }
    }
}

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize charts first
    const dashboard = new OptionScalpDashboard();
    dashboard.chartManager.initializeCharts();

    // Make dashboard available globally for debugging
    window.dashboard = dashboard;
});
