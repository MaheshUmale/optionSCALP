const ws = new WebSocket(`ws://${window.location.host}/ws`);

let idxChart, optChart, idxSeries, optSeries;

function initCharts() {
    const chartOptions = {
        layout: { background: { type: 'solid', color: '#0c0d10' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#1a1b22' }, horzLines: { color: '#1a1b22' } },
        crosshair: { mode: 1 }, // CrosshairMode.Normal
        timeScale: { borderColor: '#2b2b3b', timeVisible: true, secondsVisible: false },
        localization: { locale: 'en-US' }
    };

    idxChart = LightweightCharts.createChart(document.getElementById('index-chart'), chartOptions);
    optChart = LightweightCharts.createChart(document.getElementById('option-chart'), chartOptions);

    idxSeries = idxChart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });
    optSeries = optChart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });

    window.addEventListener('resize', () => {
        idxChart.resize(document.getElementById('index-chart').clientWidth, document.getElementById('index-chart').clientHeight);
        optChart.resize(document.getElementById('option-chart').clientWidth, document.getElementById('option-chart').clientHeight);
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
            document.getElementById('replay-slider').value = data.option_data.length;
        }

        if (data.index_data && idxSeries) {
            idxSeries.setData(data.index_data.map(d => ({
                time: new Date(d.datetime).getTime() / 1000,
                open: d.open, high: d.high, low: d.low, close: d.close
            })));
        }

        if (data.option_data && optSeries) {
            const optMapped = data.option_data.map(d => ({
                time: new Date(d.datetime).getTime() / 1000,
                open: d.open, high: d.high, low: d.low, close: d.close
            }));
            optSeries.setData(optMapped);

            if (data.markers && typeof optSeries.setMarkers === 'function') {
                optSeries.setMarkers(data.markers.map(m => ({
                    ...m,
                    time: new Date(m.time).getTime() / 1000
                })));
            }
        }

        if (data.footprint) updateFootprint(data.footprint);
        if (data.signal) updateSignal(data.signal);

        document.getElementById('status').innerText = `Status: Connected | Sym: ${data.option_symbol || 'REPLAY'}`;
    }
};

function updateFootprint(clusters) {
    const container = document.getElementById('footprint-container');
    container.innerHTML = '';
    clusters.sort((a,b) => b.price - a.price);
    clusters.forEach(c => {
        const row = document.createElement('div');
        row.className = 'fp-row' + (c.is_poc ? ' fp-poc' : '');
        const buyImbalance = c.buy > c.sell * 2.5 && c.buy > 10;
        const sellImbalance = c.sell > c.buy * 2.5 && c.sell > 10;
        row.innerHTML = `
            <div class="fp-price">${c.price.toFixed(1)}</div>
            <div class="fp-sell ${sellImbalance ? 'imbalance' : ''}">${c.sell}</div>
            <div class="fp-buy ${buyImbalance ? 'imbalance' : ''}">${c.buy}</div>
        `;
        container.appendChild(row);
    });
}

function updateSignal(sig) {
    const list = document.getElementById('signals-list');
    const div = document.createElement('div');
    div.className = 'signal-item';
    div.innerHTML = `[${new Date().toLocaleTimeString()}] <b>BUY</b> @ ${sig.entry_price} (SL: ${sig.sl})`;
    list.prepend(div);
}

function fetchLive() { ws.send(JSON.stringify({ type: 'fetch_live', index: document.getElementById('index-select').value })); }
function startReplay() { ws.send(JSON.stringify({ type: 'start_replay', index: document.getElementById('index-select').value })); }
function pauseReplay() { ws.send(JSON.stringify({ type: 'pause_replay' })); }
function stepReplay() { ws.send(JSON.stringify({ type: 'step_replay' })); }
function onSliderChange(val) { ws.send(JSON.stringify({ type: 'set_replay_index', index: parseInt(val) })); }

window.onload = initCharts;
