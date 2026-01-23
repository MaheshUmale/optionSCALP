const ws = new WebSocket(`ws://${window.location.host}/ws`);

let idxChart, ceChart, peChart;
let idxSeries, ceSeries, peSeries;
let idxVolSeries, ceVolSeries, peVolSeries;
let ceMarkers = [], peMarkers = [];

function initCharts() {
    const chartOptions = {
        layout: { background: { type: 'solid', color: '#0c0d10' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#1a1b22' }, horzLines: { color: '#1a1b22' } },
        crosshair: { mode: 0 },
        timeScale: {
            borderColor: '#2b2b3b',
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 10,
            tickMarkFormatter: (time, tickMarkType, locale) => {
                const date = new Date(time * 1000);
                const h = String(date.getUTCHours()).padStart(2, '0');
                const m = String(date.getUTCMinutes()).padStart(2, '0');
                return `${h}:${m}`;
            }
        },
        localization: {
            locale: 'en-US',
            timeFormatter: (timestamp) => {
                const date = new Date(timestamp * 1000);
                const h = String(date.getUTCHours()).padStart(2, '0');
                const m = String(date.getUTCMinutes()).padStart(2, '0');
                return `${h}:${m}`;
            }
        }
    };

    const idxEl = document.getElementById('index-chart');
    const ceEl = document.getElementById('ce-chart');
    const peEl = document.getElementById('pe-chart');

    const candleStyle = {
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350',
        priceLineVisible: true,
        lastValueVisible: true,
        priceFormat: { type: 'price', precision: 2, minMove: 0.05 },
    };
    const volStyle = {
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        scaleMargins: { top: 0.85, bottom: 0 },
    };

    if (idxEl) {
        idxChart = LightweightCharts.createChart(idxEl, chartOptions);
        idxSeries = idxChart.addCandlestickSeries({ ...candleStyle, priceScaleId: 'right' });
        idxVolSeries = idxChart.addHistogramSeries(volStyle);
        idxChart.priceScale('right').applyOptions({ autoScale: true, borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.2 }, minimumWidth: 100 });
    }
    if (ceEl) {
        ceChart = LightweightCharts.createChart(ceEl, chartOptions);
        ceSeries = ceChart.addCandlestickSeries({ ...candleStyle, priceScaleId: 'right' });
        ceVolSeries = ceChart.addHistogramSeries(volStyle);
        ceChart.priceScale('right').applyOptions({ autoScale: true, borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.2 }, minimumWidth: 100 });
    }
    if (peEl) {
        peChart = LightweightCharts.createChart(peEl, chartOptions);
        peSeries = peChart.addCandlestickSeries({ ...candleStyle, priceScaleId: 'right' });
        peVolSeries = peChart.addHistogramSeries(volStyle);
        peChart.priceScale('right').applyOptions({ autoScale: true, borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.2 }, minimumWidth: 100 });
    }

    // Synchronize crosshairs and time scales
    const charts = [idxChart, ceChart, peChart].filter(c => c !== undefined && c !== null);
    let isSyncing = false;

    charts.forEach((chart, index) => {
        const others = charts.filter((_, i) => i !== index);

        // Sync Crosshair
        chart.subscribeCrosshairMove(param => {
            if (isSyncing) return;
            isSyncing = true;
            if (param.time) {
                others.forEach(c => c.setCrosshairPosition(undefined, param.time, undefined));
            } else {
                others.forEach(c => c.clearCrosshairPosition());
            }
            isSyncing = false;
        });

        // Sync Time Scale
        chart.timeScale().subscribeVisibleTimeRangeChange(range => {
            if (!range || isSyncing) return;
            isSyncing = true;
            others.forEach(c => {
                try {
                    c.timeScale().setVisibleRange(range);
                } catch (e) { }
            });
            isSyncing = false;
        });
    });

    window.addEventListener('resize', () => {
        const resize = (chart, id) => {
            const el = document.getElementById(id);
            if (el) chart.resize(el.clientWidth, el.clientHeight);
        };
        resize(idxChart, 'index-chart');
        resize(ceChart, 'ce-chart');
        resize(peChart, 'pe-chart');
    });
}

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
        return;
    }

    if (data.type === 'replay_info') {
        const slider = document.getElementById('replay-slider');
        slider.max = data.max_idx;
        slider.value = data.current_idx;
    }

    if (data.type === 'reset_ui') {
        ceMarkers = [];
        peMarkers = [];
        if (ceSeries) ceSeries.setMarkers([]);
        if (peSeries) peSeries.setMarkers([]);
        const signalsList = document.getElementById('signals-list');
        if (signalsList) signalsList.innerHTML = '';
        updatePnLStats(null);
        return;
    }

    if (data.type === 'error') {
        document.getElementById('status').innerText = `Error: ${data.message}`;
        alert(data.message);
        return;
    }

    if (data.type === 'live_data' || data.type === 'replay_step' || data.type === 'history_data' || data.type === 'backtest_results') {

        const i_data = data.index_data || (data.is_index ? data.data : null);
        const c_data = data.ce_data || (data.is_ce ? data.data : null);
        const p_data = data.pe_data || (data.is_pe ? data.data : null);

        if (i_data && idxSeries) {
            idxSeries.setData(i_data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
            if (idxVolSeries) idxVolSeries.setData(i_data.map(d => ({ time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350' })));
            if ((data.type === 'live_data' || data.type === 'backtest_results') && idxChart) setTimeout(() => idxChart.timeScale().fitContent(), 100);
        }

        if (c_data && ceSeries) {
            ceSeries.setData(c_data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
            if (ceVolSeries) ceVolSeries.setData(c_data.map(d => ({ time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350' })));
            if ((data.type === 'live_data' || data.type === 'backtest_results') && ceChart) setTimeout(() => ceChart.timeScale().fitContent(), 100);
            if (data.ce_markers) {
                ceMarkers = data.ce_markers;
                ceSeries.setMarkers(ceMarkers);
            }
        }

        if (p_data && peSeries) {
            peSeries.setData(p_data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
            if (peVolSeries) peVolSeries.setData(p_data.map(d => ({ time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350' })));
            if ((data.type === 'live_data' || data.type === 'backtest_results') && peChart) setTimeout(() => peChart.timeScale().fitContent(), 100);
            if (data.pe_markers) {
                peMarkers = data.pe_markers;
                peSeries.setMarkers(peMarkers);
            }
        }

        if (data.index_symbol || data.index_data) {
             const sym = data.index_symbol || document.getElementById('index-select').value;
             const popout = document.getElementById('index-popout');
             if (popout) popout.href = `/chart?symbol=${sym}`;
             const label = document.getElementById('label-index');
             if (label) label.innerText = `INDEX: ${sym}`;
        }
        if (data.ce_symbol) {
            const label = document.getElementById('label-ce') || (document.getElementById('ce-label') ? document.getElementById('ce-label').querySelector('span') : null);
            if (label) label.innerText = `CE OPTION: ${data.ce_symbol}`;
            const popout = document.getElementById('ce-popout');
            if (popout) popout.href = `/chart?symbol=${data.ce_symbol}`;
        }
        if (data.pe_symbol) {
            const label = document.getElementById('label-pe') || (document.getElementById('pe-label') ? document.getElementById('pe-label').querySelector('span') : null);
            if (label) label.innerText = `PE OPTION: ${data.pe_symbol}`;
            const popout = document.getElementById('pe-popout');
            if (popout) popout.href = `/chart?symbol=${data.pe_symbol}`;
        }
        if (data.new_signals) {
            data.new_signals.forEach(sig => updateSignal(sig));
        }

        if (data.strategy_report) {
            renderStrategyReport(data.strategy_report);
        }

        document.getElementById('status').innerText = `Status: Connected | Trend: ${data.trend || 'N/A'}`;
    }

    if (data.type === 'live_update') {
        const c = data.candle;
        const v = { time: c.time, value: c.volume, color: c.close >= c.open ? '#26a69a' : '#ef5350' };

        if (data.is_index && idxSeries) {
            idxSeries.update(c);
            if (idxVolSeries) idxVolSeries.update(v);
            const dispIdx = document.getElementById('display-index-val');
            if (dispIdx) dispIdx.innerText = c.close.toFixed(2);
        } else if (data.is_ce && ceSeries) {
            ceSeries.update(c);
            if (ceVolSeries) ceVolSeries.update(v);
        } else if (data.is_pe && peSeries) {
            peSeries.update(c);
            if (peVolSeries) peVolSeries.update(v);
        }
    }

    if (data.type === 'delta_signals' && data.delta_signals) {
        updateDeltaSignal(data.delta_signals);
    }

    if (data.pcr_insights) {
        updatePCRInsights(data.pcr_insights);
        if (document.getElementById('display-pcr')) {
            document.getElementById('display-pcr').innerText = `${data.pcr_insights.pcr} (${data.pcr_insights.buildup_status || 'NEUTRAL'})`;
        }
    }

    if (data.trend) {
        if (document.getElementById('display-trend')) {
             document.getElementById('display-trend').innerText = data.trend;
        }
    }

    if (data.option_chain) {
        // Option Chain logic could be added here for Greeks/OI visualization
        console.log("Option Chain Update:", data.option_chain);
    }

    if (data.pnl_stats) {
        updatePnLStats(data.pnl_stats);
    }

    if (data.type === 'marker_update') {
        if (data.is_ce) {
            ceMarkers.push(data.marker);
            if (ceSeries) ceSeries.setMarkers(ceMarkers);
        }
        if (data.is_pe) {
            peMarkers.push(data.marker);
            if (peSeries) peSeries.setMarkers(peMarkers);
        }
        if (data.signal) updateSignal(data.signal);
    }
};

function updateSignal(sig) {
    const list = document.getElementById('signals-list');
    if (!list) return;

    // Prevent duplicates in the UI
    const timeStr = sig.time ? new Date((sig.time - 19800) * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();
    const sigId = `${sig.strat_name}-${sig.time}-${sig.entry_price}`;
    if (document.getElementById(sigId)) return;

    const div = document.createElement('div');
    div.id = sigId;
    div.className = 'signal-item';
    const strat = sig.strat_name || "STRATEGY";
    const side = (sig.type && sig.type.includes("PE")) ? "PE" : "CE";
    const color = side === "CE" ? "#26a69a" : "#ef5350";

    div.style.borderLeft = `4px solid ${color}`;
    div.title = sig.reason || ""; // Tooltip
    div.innerHTML = `[${timeStr}] <b>${strat}</b> (${side}) @ ${sig.entry_price.toFixed(2)} (SL: ${sig.sl ? sig.sl.toFixed(2) : 'N/A'})<br><small style="color: #888;">${sig.reason || ''}</small>`;
    list.prepend(div);

    // Limit log entries to 50
    if (list.children.length > 50) {
        list.removeChild(list.lastChild);
    }
}

function renderStrategyReport(report) {
    let reportEl = document.getElementById('strategy-report');
    if (!reportEl) {
        const container = document.createElement('div');
        container.id = 'strategy-report-container';
        container.className = 'dashboard-card';
        container.style.marginTop = '20px';
        container.innerHTML = '<h3>STRATEGY PERFORMANCE</h3><div id="strategy-report"></div>';
        const main = document.querySelector('.main-container');
        if (main) main.appendChild(container);
        reportEl = document.getElementById('strategy-report');
    }

    let html = '<table class="report-table"><thead><tr><th>Strategy</th><th>Trades</th><th>Win Rate</th><th>Net PnL</th></tr></thead><tbody>';
    for (const [name, stats] of Object.entries(report)) {
        const color = stats.pnl >= 0 ? '#26a69a' : '#ef5350';
        html += `<tr>
            <td>${name}</td>
            <td>${stats.total}</td>
            <td>${stats.win_rate}%</td>
            <td style="color: ${color}; font-weight: bold;">₹${stats.pnl.toFixed(2)}</td>
        </tr>`;
    }
    html += '</tbody></table>';
    reportEl.innerHTML = html;
}

function updateDeltaSignal(sig) {
    const list = document.getElementById('signals-list');
    if (!list) return;
    const div = document.createElement('div');
    div.className = 'signal-item delta-signal';
    const color = sig.type === 'BULLISH' ? '#26a69a' : '#ef5350';
    div.style.borderLeft = `4px solid ${color}`;
    div.innerHTML = `[${new Date().toLocaleTimeString()}] <b>${sig.type}</b> (Delta: ${sig.net_delta.toFixed(0)})<br>Strikes: ${sig.strikes.join(', ')}`;
    list.prepend(div);
}

function updatePCRInsights(pcr) {
    const statusEl = document.getElementById('status');
    const parts = statusEl.innerText.split('|');
    const currentText = parts[0];
    const trendText = parts[1] || "";
    const buildup = pcr.buildup_status ? ` | ${pcr.buildup_status}` : "";
    statusEl.innerHTML = `${currentText} | ${trendText} | PCR: ${pcr.pcr} (${pcr.pcr_change > 1 ? '▲' : '▼'})${buildup}`;
}

function updatePnLStats(stats) {
    let statsEl = document.getElementById('pnl-stats');
    if (!statsEl) {
        statsEl = document.createElement('div');
        statsEl.id = 'pnl-stats';
        statsEl.className = 'pnl-stats-overlay';
        document.body.appendChild(statsEl);
    }
    if (!stats) {
        statsEl.innerHTML = `
            <div style="font-size: 10px; color: #888;">PnL STATS</div>
            <div style="font-size: 16px; font-weight: bold; color: #888;">₹0.00</div>
            <div style="font-size: 11px;">Closed: 0 | Open: 0</div>
            <div style="font-size: 11px;">Win: 0 | Loss: 0 | WR: 0%</div>
        `;
        return;
    }
    const color = stats.total_pnl >= 0 ? '#26a69a' : '#ef5350';
    statsEl.innerHTML = `
        <div style="font-size: 10px; color: #888;">PnL STATS (Closed)</div>
        <div style="font-size: 18px; font-weight: bold; color: ${color};">₹${stats.total_pnl.toFixed(2)}</div>
        <div style="font-size: 11px;">Closed: ${stats.total_closed} | Open: ${stats.total_trades - stats.total_closed}</div>
        <div style="font-size: 11px;">Win: ${stats.win_count} | Loss: ${stats.loss_count} | WR: ${stats.win_rate}%</div>
    `;

    // Also update dashboard PnL card if it exists
    const dashPnl = document.getElementById('dashboard-pnl');
    if (dashPnl) {
        dashPnl.querySelector('.pnl-main').innerText = `₹${stats.total_pnl.toFixed(2)}`;
        dashPnl.querySelector('.pnl-main').style.color = color;
        dashPnl.querySelector('.pnl-sub').innerText = `Wins: ${stats.win_count} | Losses: ${stats.loss_count} | WR: ${stats.win_rate}%`;
    }
}

function fetchLive() { ws.send(JSON.stringify({ type: 'fetch_live', index: document.getElementById('index-select').value })); }
function runFullBacktest() {
    ws.send(JSON.stringify({
        type: 'run_backtest',
        index: document.getElementById('index-select').value,
        date: document.getElementById('replay-date').value
    }));
}

window.onload = () => {
    initCharts();
    updatePnLStats(null);
};
