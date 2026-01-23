/**
 * OptionScalp Pro - Main Controller
 */

import { ChartManager } from './charts/manager.js';

class CommandController {
    constructor() {
        this.chartManager = new ChartManager();
        this.ws = null;
        this.currentMode = 'LIVE'; // LIVE or REPLAY
        this.currentIndex = 'BANKNIFTY';
        this.symbols = {
            index: 'BANKNIFTY',
            ce: '--',
            pe: '--'
        };

        this.init();
    }

    init() {
        this.chartManager.initializeCharts();
        this.setupEventListeners();
        this.connect();
    }

    setupEventListeners() {
        // Mode Switches
        document.getElementById('btn-mode-live').addEventListener('click', () => this.switchMode('LIVE'));
        document.getElementById('btn-mode-replay').addEventListener('click', () => this.switchMode('REPLAY'));

        // Index Selection
        document.getElementById('index-select').addEventListener('change', (e) => {
            this.currentIndex = e.target.value;
            this.symbols.index = this.currentIndex;
            this.updateLabels();
            if (this.currentMode === 'LIVE') {
                this.fetchLive();
            }
        });

        // Replay Controls
        document.getElementById('btn-replay-start').addEventListener('click', () => this.startReplay());
        document.getElementById('btn-replay-play').addEventListener('click', () => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'replay_control', action: 'play' }));
            }
        });
        document.getElementById('btn-replay-pause').addEventListener('click', () => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'replay_control', action: 'pause' }));
            }
        });
    }

    switchMode(mode) {
        this.currentMode = mode;
        const liveBtn = document.getElementById('btn-mode-live');
        const replayBtn = document.getElementById('btn-mode-replay');
        const replayControls = document.getElementById('replay-controls');

        if (mode === 'REPLAY') {
            liveBtn.classList.remove('active');
            replayBtn.classList.add('active');
            replayControls.style.display = 'flex';
            this.chartManager.clearAllCharts();
            this.resetUI();
            this.updateLabels();
        } else {
            liveBtn.classList.add('active');
            replayBtn.classList.remove('active');
            replayControls.style.display = 'none';
            this.fetchLive();
        }
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            document.getElementById('status-dot').style.background = '#10B981';
            document.getElementById('status-text').textContent = 'Connected';
            if (this.currentMode === 'LIVE') this.fetchLive();
        };

        this.ws.onclose = () => {
            document.getElementById('status-dot').style.background = '#EF4444';
            document.getElementById('status-text').textContent = 'Disconnected';
            setTimeout(() => this.connect(), 3000);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
    }

    handleMessage(data) {
        if (data.type === 'live_data' || data.type === 'replay_step' || data.type === 'history_data') {
            this.updateUI(data);

            // Replay progress update with strict check for 0
            if (data.current_idx !== undefined && data.max_idx !== undefined) {
                const counter = document.getElementById('replay-time');
                if (counter) counter.textContent = `${data.current_idx} / ${data.max_idx}`;
            }

            // Sync charts only on full data load
            if (data.type === 'live_data' || data.type === 'history_data') {
                setTimeout(() => this.chartManager.handleResize(), 100);
            }
        } else if (data.type === 'live_update') {
            this.handleTick(data);
        } else if (data.type === 'replay_info') {
            const counter = document.getElementById('replay-time');
            if (counter) counter.textContent = `0 / ${data.max_idx}`;
        } else if (data.type === 'pcr_update') {
            this.updateMarketContext(data.pcr_insights);
        }
    }

    updateUI(data) {
        // Update Symbols & Labels
        if (data.index_symbol) this.symbols.index = data.index_symbol;
        if (data.ce_symbol) this.symbols.ce = data.ce_symbol;
        if (data.pe_symbol) this.symbols.pe = data.pe_symbol;
        this.updateLabels();

        // Update Charts
        if (data.index_data) this.chartManager.updateChartData('index', data.index_data);
        if (data.ce_data) this.chartManager.updateChartData('ce', data.ce_data);
        if (data.pe_data) this.chartManager.updateChartData('pe', data.pe_data);

        // Update Markers
        if (data.ce_markers) this.chartManager.setMarkers('ce', data.ce_markers);
        if (data.pe_markers) this.chartManager.setMarkers('pe', data.pe_markers);

        // Update Action Stream
        if (data.new_signals) {
            data.new_signals.forEach(s => this.addToStream(s));
        }

        // Update Stats
        if (data.pnl_stats) this.updatePnL(data.pnl_stats);
        if (data.trend) document.getElementById('market-trend').textContent = data.trend;
        if (data.pcr_insights) this.updateMarketContext(data.pcr_insights);
    }

    handleTick(data) {
        // Find which chart to update
        let chartId = null;
        if (data.symbol === this.symbols.index || data.symbol.replace("NSE:", "") === this.symbols.index.replace("NSE:", "")) chartId = 'index';
        else if (data.symbol === this.symbols.ce || data.symbol.replace("NSE:", "") === this.symbols.ce.replace("NSE:", "")) chartId = 'ce';
        else if (data.symbol === this.symbols.pe || data.symbol.replace("NSE:", "") === this.symbols.pe.replace("NSE:", "")) chartId = 'pe';

        if (chartId) {
            this.chartManager.updateLiveCandle(chartId, data.candle);
        }
    }

    addToStream(signal) {
        const container = document.getElementById('action-stream');
        if (!container) return;

        const el = document.createElement('div');
        const isBullish = signal.type === 'LONG' || signal.symbol?.includes('CE');
        el.className = `stream-item ${isBullish ? 'bullish' : 'bearish'}`;

        // Robust 24h Formatter
        const d = new Date(signal.time * 1000);
        const time = d.getUTCHours().toString().padStart(2, '0') + ':' +
            d.getUTCMinutes().toString().padStart(2, '0') + ':' +
            d.getUTCSeconds().toString().padStart(2, '0');

        el.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="font-weight:700;">${signal.strat_name || 'SIGNAL'}</span>
                <span style="color:#8B949E; font-family:monospace;">${time}</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span>${signal.reason || 'Entry Confirmation'}</span>
                <span style="font-weight:800; font-size:14px;">${signal.entry_price ? signal.entry_price.toFixed(2) : '--'}</span>
            </div>
        `;
        container.prepend(el);

        // Trim stream
        if (container.children.length > 50) container.lastChild.remove();
    }

    updateLabels() {
        const set = (id, txt) => {
            const el = document.getElementById(id);
            if (el) el.textContent = txt.replace("NSE:", "");
        };
        set('index-symbol', this.symbols.index);
        set('ce-symbol', this.symbols.ce);
        set('pe-symbol', this.symbols.pe);
    }

    updatePnL(stats) {
        const pnlEl = document.getElementById('pnl-main-value');
        if (pnlEl) {
            pnlEl.textContent = `₹${stats.total_pnl.toFixed(2)}`;
            pnlEl.style.color = stats.total_pnl >= 0 ? '#10B981' : '#EF4444';
        }

        const wrFill = document.getElementById('win-rate-fill');
        if (wrFill) wrFill.style.width = `${stats.win_rate}%`;

        const wrText = document.getElementById('win-rate-text');
        if (wrText) wrText.textContent = `Win Rate: ${stats.win_rate.toFixed(1)}%`;

        this.updateAnalysis(stats);
    }

    updateAnalysis(stats) {
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };
        set('ana-dd', `₹${stats.max_drawdown?.toFixed(2) || 0}`);
        set('ana-avg-win', `₹${stats.avg_win?.toFixed(2) || 0}`);
        set('ana-avg-loss', `₹${stats.avg_loss?.toFixed(2) || 0}`);

        const rr = (stats.avg_loss && stats.avg_loss !== 0) ? Math.abs(stats.avg_win / stats.avg_loss) : 0;
        set('ana-rr', rr.toFixed(2));
    }

    updateMarketContext(insights) {
        const pcrVal = document.getElementById('pcr-value');
        if (pcrVal) pcrVal.textContent = insights.pcr?.toFixed(2) || '--';

        const pcrStatus = document.getElementById('pcr-status');
        if (pcrStatus) {
            const status = insights.buildup_status || 'NEUTRAL';
            pcrStatus.textContent = status;
            pcrStatus.className = `badge ${status.includes('LONG') ? 'badge-success' : (status.includes('SHORT') ? 'badge-danger' : 'badge-neutral')}`;
        }
    }

    fetchLive() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const idx = document.getElementById('index-select').value;
            this.symbols.index = idx;
            this.updateLabels();
            this.ws.send(JSON.stringify({ type: 'fetch_live', index: idx }));
        }
    }

    startReplay() {
        const dateStr = document.getElementById('replay-date').value;
        if (!dateStr) return;

        const idx = document.getElementById('index-select').value;
        this.symbols.index = idx;
        this.updateLabels();
        this.resetUI();

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'start_replay',
                index: idx,
                date: dateStr
            }));
        }
    }

    resetUI() {
        document.getElementById('action-stream').innerHTML = '';
        document.getElementById('positions-list').innerHTML = '';
        const counter = document.getElementById('replay-time');
        if (counter) counter.textContent = '0 / 0';
    }
}

// Controller entry point
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new CommandController();
});
