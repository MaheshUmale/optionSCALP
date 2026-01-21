const ws = new WebSocket(`ws://${window.location.host}/ws`);

let idxChart, ceChart, peChart;
let idxSeries, ceSeries, peSeries;
let idxVolSeries, ceVolSeries, peVolSeries;

function initCharts() {
    const chartOptions = {
        layout: { background: { type: 'solid', color: '#0c0d10' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#1a1b22' }, horzLines: { color: '#1a1b22' } },
        crosshair: { mode: 1 },
        timeScale: { borderColor: '#2b2b3b', timeVisible: true, secondsVisible: false },
        localization: { locale: 'en-US' }
    };

    idxChart = LightweightCharts.createChart(document.getElementById('index-chart'), chartOptions);
    ceChart = LightweightCharts.createChart(document.getElementById('ce-chart'), chartOptions);
    peChart = LightweightCharts.createChart(document.getElementById('pe-chart'), chartOptions);

    const candleStyle = {
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    };

    idxSeries = idxChart.addCandlestickSeries(candleStyle);
    ceSeries = ceChart.addCandlestickSeries(candleStyle);
    peSeries = peChart.addCandlestickSeries(candleStyle);

    const volStyle = {
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        scaleMargins: { top: 0.8, bottom: 0 },
    };

    idxVolSeries = idxChart.addHistogramSeries(volStyle);
    ceVolSeries = ceChart.addHistogramSeries(volStyle);
    peVolSeries = peChart.addHistogramSeries(volStyle);

    // Synchronize crosshairs and time scales
    const charts = [idxChart, ceChart, peChart];

    charts.forEach((chart, index) => {
        const others = charts.filter((_, i) => i !== index);

        // Sync Crosshair
        chart.subscribeCrosshairMove(param => {
            if (param.time) {
                others.forEach(c => c.setCrosshairPosition(undefined, param.time, undefined));
            } else {
                others.forEach(c => c.clearCrosshairPosition());
            }
        });

        // Sync Time Scale
        chart.timeScale().subscribeVisibleTimeRangeChange(range => {
            if (!range) return;
            others.forEach(c => {
                c.timeScale().setVisibleRange(range);
            });
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

    if (data.type === 'replay_info') {
        const slider = document.getElementById('replay-slider');
        slider.max = data.max_idx;
        slider.value = data.current_idx;
    }

    if (data.type === 'live_data' || data.type === 'replay_step') {
        if (data.type === 'replay_step') {
            document.getElementById('replay-slider').value = data.max_idx || 0;
        }

        if (data.index_data && idxSeries) {
            idxSeries.setData(data.index_data.map(d => ({
                time: d.time,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
            idxVolSeries.setData(data.index_data.map(d => ({
                time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350'
            })));
        }

        if (data.ce_data && ceSeries) {
            ceSeries.setData(data.ce_data.map(d => ({
                time: d.time,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
            ceVolSeries.setData(data.ce_data.map(d => ({
                time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350'
            })));
            if (data.ce_markers) ceSeries.setMarkers(data.ce_markers);
        }

        if (data.pe_data && peSeries) {
            peSeries.setData(data.pe_data.map(d => ({
                time: d.time,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
            peVolSeries.setData(data.pe_data.map(d => ({
                time: d.time, value: d.volume, color: d.close >= d.open ? '#26a69a' : '#ef5350'
            })));
            if (data.pe_markers) peSeries.setMarkers(data.pe_markers);
        }

        if (data.ce_symbol) document.getElementById('ce-label').innerText = `CE OPTION: ${data.ce_symbol}`;
        if (data.pe_symbol) document.getElementById('pe-label').innerText = `PE OPTION: ${data.pe_symbol}`;
        if (data.signal) updateSignal(data.signal);

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

    if (data.type === 'marker_update') {
        if (data.is_ce) ceSeries.setMarkers([...ceSeries.markers() || [], data.marker]);
        if (data.is_pe) peSeries.setMarkers([...peSeries.markers() || [], data.marker]);
        if (data.signal) updateSignal(data.signal);
    }
};

function updateSignal(sig) {
    const list = document.getElementById('signals-list');
    const div = document.createElement('div');
    div.className = 'signal-item';
    div.innerHTML = `[${new Date().toLocaleTimeString()}] <b>BUY</b> @ ${sig.entry_price} (SL: ${sig.sl})`;
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

function fetchLive() { ws.send(JSON.stringify({ type: 'fetch_live', index: document.getElementById('index-select').value })); }
function startReplay() { ws.send(JSON.stringify({ type: 'start_replay', index: document.getElementById('index-select').value })); }
function pauseReplay() { ws.send(JSON.stringify({ type: 'pause_replay' })); }
function stepReplay() { ws.send(JSON.stringify({ type: 'step_replay' })); }
function onSliderChange(val) { ws.send(JSON.stringify({ type: 'set_replay_index', index: parseInt(val) })); }

window.onload = initCharts;
