const ws = new WebSocket(`ws://${window.location.host}/ws`);
let idxSeries, optSeries, idxChart, optChart;

function init() {
    console.log("Initializing charts...");
    const cfg = {
        layout: { background: { type: 'solid', color: '#0c0d10' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#161921' }, horzLines: { color: '#161921' } },
        timeScale: { borderColor: '#2b2b3b', timeVisible: true },
        localization: { locale: 'en-US' }
    };

    idxChart = LightweightCharts.createChart(document.getElementById('idx-chart'), cfg);
    optChart = LightweightCharts.createChart(document.getElementById('opt-chart'), cfg);
    idxSeries = idxChart.addCandlestickSeries({ upColor: '#26a69a', downColor: '#ef5350' });
    optSeries = optChart.addCandlestickSeries({ upColor: '#26a69a', downColor: '#ef5350' });

    const resize = () => {
        idxChart.resize(document.getElementById('idx-chart').clientWidth, document.getElementById('idx-chart').clientHeight);
        optChart.resize(document.getElementById('opt-chart').clientWidth, document.getElementById('opt-chart').clientHeight);
    }
    window.addEventListener('resize', resize);
    setTimeout(resize, 200);

    ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.index) idxSeries.setData(d.index);
        if (d.option) optSeries.setData(d.option);
        if (d.footprint) updateFP(d.footprint);
        document.getElementById('status').innerText = "Streaming: " + d.option_symbol;
    }
}

function updateFP(data) {
    const div = document.getElementById('fp');
    div.innerHTML = data.sort((a,b) => b.price - a.price).map(c => `
        <div class="fp-row ${c.is_poc ? 'fp-poc' : ''}">
            <div class="fp-price">${c.price.toFixed(1)}</div>
            <div class="fp-sell">${c.sell}</div>
            <div class="fp-buy">${c.buy}</div>
        </div>
    `).join('');
}

function start() { ws.send(JSON.stringify({type:'start'})); }
function pause() { ws.send(JSON.stringify({type:'pause'})); }

window.onload = init;
