const ws = new WebSocket(`ws://${window.location.host}/ws`);

let idxChart, optChart, idxSeries, optSeries;

function initCharts() {
    const chartOptions = {
        layout: { background: { type: 'solid', color: '#0c0d10' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#1a1b22' }, horzLines: { color: '#1a1b22' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        timeScale: { borderColor: '#2b2b3b', timeVisible: true, secondsVisible: false }
    };

    const idxContainer = document.getElementById('index-chart');
    const optContainer = document.getElementById('option-chart');

    idxChart = LightweightCharts.createChart(idxContainer, chartOptions);
    optChart = LightweightCharts.createChart(optContainer, chartOptions);

    idxSeries = idxChart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });
    optSeries = optChart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });

    window.addEventListener('resize', () => {
        idxChart.resize(idxContainer.clientWidth, idxContainer.clientHeight);
        optChart.resize(optContainer.clientWidth, optContainer.clientHeight);
    });
}

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'live_data' || data.type === 'replay_step') {
        let currentOptTime = null;

        if (data.index_data && data.index_data.length > 0 && idxSeries) {
            const idxData = data.index_data.map(d => ({
                time: new Date(d.datetime).getTime() / 1000,
                open: d.open, high: d.high, low: d.low, close: d.close
            }));
            idxSeries.setData(idxData);
        }

        if (data.option_data && data.option_data.length > 0 && optSeries) {
            const optData = data.option_data.map(d => ({
                time: new Date(d.datetime).getTime() / 1000,
                open: d.open, high: d.high, low: d.low, close: d.close
            }));
            optSeries.setData(optData);
            currentOptTime = optData[optData.length-1].time;
        }

        if (data.footprint) {
            updateFootprint(data.footprint);
        }

        if (data.signal && currentOptTime && optSeries) {
            optSeries.setMarkers([{
                time: currentOptTime,
                position: "belowBar",
                color: "#2196F3",
                shape: "arrowUp",
                text: "BUY SIGNAL"
            }]);
            updateSignal(data.signal);
        }

        document.getElementById('status').innerText = `Status: Connected | Sym: ${data.option_symbol || 'REPLAY'}`;
    }
};

ws.onopen = () => { document.getElementById('status').innerText = "Status: Connected"; };

function updateFootprint(clusters) {
    const container = document.getElementById('footprint-container');
    container.innerHTML = '';
    clusters.sort((a,b) => b.price - a.price);
    clusters.forEach(c => {
        const row = document.createElement('div');
        row.className = 'fp-row';
        const buyImbalance = c.buy > c.sell * 3;
        const sellImbalance = c.sell > c.buy * 3;
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
    div.innerHTML = `[${new Date().toLocaleTimeString()}] <b>BUY</b> @ ${sig.entry_price} (SL: ${sig.sl})`;
    list.prepend(div);
}

function fetchLive() { ws.send(JSON.stringify({ type: 'fetch_live', index: document.getElementById('index-select').value })); }
function startReplay() { ws.send(JSON.stringify({ type: 'start_replay', index: document.getElementById('index-select').value })); }
function pauseReplay() { ws.send(JSON.stringify({ type: 'pause_replay' })); }
function stepReplay() { ws.send(JSON.stringify({ type: 'step_replay' })); }

window.onload = initCharts;
