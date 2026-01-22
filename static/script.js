const ws = new WebSocket(`ws://${window.location.host}/ws`);

let idxChart, ceChart, peChart;
let idxSeries, ceSeries, peSeries;
let idxVolSeries, ceVolSeries, peVolSeries;

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

    idxChart = LightweightCharts.createChart(document.getElementById('index-chart'), chartOptions);
    ceChart = LightweightCharts.createChart(document.getElementById('ce-chart'), chartOptions);
    peChart = LightweightCharts.createChart(document.getElementById('pe-chart'), chartOptions);

    const candleStyle = {
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    };

    idxSeries = idxChart.addCandlestickSeries({
        ...candleStyle,
        priceScaleId: 'right'
    });
    ceSeries = ceChart.addCandlestickSeries({
        ...candleStyle,
        priceScaleId: 'right'
    });
    peSeries = peChart.addCandlestickSeries({
        ...candleStyle,
        priceScaleId: 'right'
    });

    [idxChart, ceChart, peChart].forEach(c => {
        c.priceScale('right').applyOptions({
            autoScale: true,
            borderVisible: false,
            scaleMargins: { top: 0.1, bottom: 0.2 },
        });
    });

    const volStyle = {
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        scaleMargins: { top: 0.85, bottom: 0 },
    };

    idxVolSeries = idxChart.addHistogramSeries(volStyle);
    ceVolSeries = ceChart.addHistogramSeries(volStyle);
    peVolSeries = peChart.addHistogramSeries(volStyle);

    // Synchronize crosshairs and time scales
    const charts = [idxChart, ceChart, peChart];
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
                c.timeScale().setVisibleRange(range);
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
    // Log message for debugging
    // console.log("Received:", data.type);
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
        if (ceSeries) ceSeries.setMarkers([]);
        if (peSeries) peSeries.setMarkers([]);
        document.getElementById('signals-list').innerHTML = '';
        updatePnLStats(null);
        return;
    }

    if (data.type === 'error') {
        document.getElementById('status').innerText = `Error: ${data.message}`;
        alert(data.message);
        return;
    }

    if (data.type === 'live_data' || data.type === 'replay_step') {
        if (data.type === 'replay_step') {
            const slider = document.getElementById('replay-slider');
            if (data.max_idx) slider.max = data.max_idx;
            if (data.current_idx) slider.value = data.current_idx;
        }

        if (data.index_data && idxSeries) {
            idxSeries.setData(data.index_data.map(d => ({
                time: d.time,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
            idxVolSeries.setData(data.index_data.map(d => ({
                time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350'
            })));
            idxChart.timeScale().fitContent();
        }

        if (data.ce_data && ceSeries) {
            ceSeries.setData(data.ce_data.map(d => ({
                time: d.time,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
            ceVolSeries.setData(data.ce_data.map(d => ({
                time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350'
            })));
            if (data.ce_markers) {
                ceSeries.setMarkers(data.ce_markers);
            }
            ceChart.timeScale().fitContent();
        }

        if (data.pe_data && peSeries) {
            peSeries.setData(data.pe_data.map(d => ({
                time: d.time,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
            peVolSeries.setData(data.pe_data.map(d => ({
                time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350'
            })));
            if (data.pe_markers) {
                peSeries.setMarkers(data.pe_markers);
            }
            peChart.timeScale().fitContent();
        }

        if (data.index_symbol || data.index_data) {
             const sym = data.index_symbol || document.getElementById('index-select').value;
             document.getElementById('index-popout').href = `/chart?symbol=${sym}`;
        }
        if (data.ce_symbol) {
            document.getElementById('ce-label').querySelector('span').innerText = `CE OPTION: ${data.ce_symbol}`;
            document.getElementById('ce-popout').href = `/chart?symbol=${data.ce_symbol}`;
        }
        if (data.pe_symbol) {
            document.getElementById('pe-label').querySelector('span').innerText = `PE OPTION: ${data.pe_symbol}`;
            document.getElementById('pe-popout').href = `/chart?symbol=${data.pe_symbol}`;
        }
        if (data.new_signals) {
            data.new_signals.forEach(sig => updateSignal(sig));
        }

        document.getElementById('status').innerText = `Status: Connected | Trend: ${data.trend || 'N/A'}`;
    }

    if (data.type === 'live_update') {
        const c = data.candle;
        const v = { time: c.time, value: c.volume, color: c.close >= c.open ? '#26a69a' : '#ef5350' };

        if (data.is_index) {
            idxSeries.update(c);
            idxVolSeries.update(v);
        } else if (data.is_ce) {
            ceSeries.update(c);
            ceVolSeries.update(v);
        } else if (data.is_pe) {
            peSeries.update(c);
            peVolSeries.update(v);
        }
    }

    if (data.type === 'delta_signals' && data.delta_signals) {
        updateDeltaSignal(data.delta_signals);
    }

    if (data.pcr_insights) {
        updatePCRInsights(data.pcr_insights);
    }

    if (data.option_chain) {
        // Option Chain logic could be added here for Greeks/OI visualization
        console.log("Option Chain Update:", data.option_chain);
    }

    if (data.pnl_stats) {
        updatePnLStats(data.pnl_stats);
    }

    if (data.type === 'marker_update') {
        if (data.is_ce) ceSeries.setMarkers([...ceSeries.markers() || [], data.marker]);
        if (data.is_pe) peSeries.setMarkers([...peSeries.markers() || [], data.marker]);
        if (data.signal) updateSignal(data.signal);
    }
};

function updateSignal(sig) {
    const list = document.getElementById('signals-list');
    if (list.style.display === 'none') {
        // Auto-show if new signal comes? Or just pulse the header?
    }
    const div = document.createElement('div');
    div.className = 'signal-item';
    const strat = sig.strat_name || "STRATEGY";
    const side = (sig.type && sig.type.includes("PE")) ? "PE" : "CE";
    const color = side === "CE" ? "#26a69a" : "#ef5350";

    // For replay mode, sig.time is the shifted IST unix timestamp.
    const timeStr = sig.time ? new Date((sig.time - 19800) * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();

    div.style.borderLeft = `4px solid ${color}`;
    div.innerHTML = `[${timeStr}] <b>${strat}</b> (${side}) @ ${sig.entry_price.toFixed(2)} (SL: ${sig.sl.toFixed(2)})`;
    list.prepend(div);
}

function updateDeltaSignal(sig) {
    const list = document.getElementById('signals-list');
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
}

function fetchLive() { ws.send(JSON.stringify({ type: 'fetch_live', index: document.getElementById('index-select').value })); }
function startReplay() {
    ws.send(JSON.stringify({
        type: 'start_replay',
        index: document.getElementById('index-select').value,
        date: document.getElementById('replay-date') ? document.getElementById('replay-date').value : null
    }));
}
function pauseReplay() { ws.send(JSON.stringify({ type: 'pause_replay' })); }
function stepReplay() { ws.send(JSON.stringify({ type: 'step_replay' })); }
function setReplaySpeed(val) { ws.send(JSON.stringify({ type: 'set_replay_speed', speed: parseFloat(val) })); }
function onSliderChange(val) { ws.send(JSON.stringify({ type: 'set_replay_index', index: parseInt(val) })); }

window.onload = () => {
    initCharts();
    updatePnLStats(null);
};
