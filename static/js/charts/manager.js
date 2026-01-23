/**
 * OptionScalp Pro - Chart Manager
 */

import { CONFIG } from '../config.js';

export class ChartManager {
    constructor() {
        this.charts = {};
        this.series = {};
        this.volumeSeries = {};
        this.markers = {
            ce: [],
            pe: []
        };
        this.isSyncing = false;
    }

    initializeCharts() {
        // Initialize Index Chart
        this.createChart('index', 'index-chart');

        // Initialize CE Chart
        this.createChart('ce', 'ce-chart');

        // Initialize PE Chart
        this.createChart('pe', 'pe-chart');

        // Setup synchronization
        this.synchronizeCharts();

        // Setup resize handling
        window.addEventListener('resize', () => this.handleResize());
    }

    createChart(id, elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error(`Chart element ${elementId} not found`);
            return;
        }

        // Create chart instance
        const chart = LightweightCharts.createChart(element, CONFIG.CHART_OPTIONS);

        // Add candlestick series
        const candleSeries = chart.addCandlestickSeries({
            ...CONFIG.CANDLESTICK_STYLE,
            priceScaleId: 'right'
        });

        // Configure price scale
        chart.priceScale('right').applyOptions({
            autoScale: true,
            borderVisible: false,
            scaleMargins: { top: 0.1, bottom: 0.2 },
            minimumWidth: 100
        });

        // Add volume series
        const volumeSeries = chart.addHistogramSeries(CONFIG.VOLUME_STYLE);

        // Store references
        this.charts[id] = chart;
        this.series[id] = candleSeries;
        this.volumeSeries[id] = volumeSeries;
    }

    synchronizeCharts() {
        const chartList = Object.values(this.charts).filter(c => c !== undefined);

        chartList.forEach((chart, index) => {
            const others = chartList.filter((_, i) => i !== index);

            // Sync crosshair
            chart.subscribeCrosshairMove(param => {
                if (this.isSyncing) return;
                this.isSyncing = true;

                if (param.time) {
                    others.forEach(c => c.setCrosshairPosition(undefined, param.time, undefined));
                } else {
                    others.forEach(c => c.clearCrosshairPosition());
                }

                this.isSyncing = false;
            });

            // Sync time scale
            chart.timeScale().subscribeVisibleTimeRangeChange(range => {
                if (!range || this.isSyncing) return;
                this.isSyncing = true;

                others.forEach(c => {
                    try {
                        c.timeScale().setVisibleRange(range);
                    } catch (e) {
                        // Ignore errors
                    }
                });

                this.isSyncing = false;
            });
        });
    }

    updateChartData(chartId, data) {
        const series = this.series[chartId];
        const volumeSeries = this.volumeSeries[chartId];

        if (!series || !data) return;

        const candleData = data.map(d => ({
            time: d.time,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close
        }));

        const volumeData = data.map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? '#26A69A' : '#EF5350'
        }));

        series.setData(candleData);
        if (volumeSeries) {
            volumeSeries.setData(volumeData);
        }
    }

    updateLiveCandle(chartId, candle) {
        const series = this.series[chartId];
        const volumeSeries = this.volumeSeries[chartId];

        if (!series) return;

        series.update({
            time: candle.time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close
        });

        if (volumeSeries) {
            volumeSeries.update({
                time: candle.time,
                value: candle.volume,
                color: candle.close >= candle.open ? '#26A69A' : '#EF5350'
            });
        }
    }

    setMarkers(chartId, markers) {
        const series = this.series[chartId];
        if (!series) return;

        this.markers[chartId] = markers;
        series.setMarkers(markers);
    }

    addMarker(chartId, marker) {
        if (!this.markers[chartId]) {
            this.markers[chartId] = [];
        }
        this.markers[chartId].push(marker);
        this.setMarkers(chartId, this.markers[chartId]);
    }

    fitContent(chartId) {
        const chart = this.charts[chartId];
        if (chart) {
            setTimeout(() => chart.timeScale().fitContent(), 100);
        }
    }

    handleResize() {
        Object.entries(this.charts).forEach(([id, chart]) => {
            const element = chart._container;
            if (element) {
                chart.resize(element.clientWidth, element.clientHeight);
            }
        });
    }

    clearChart(chartId) {
        const series = this.series[chartId];
        if (series) {
            series.setData([]);
        }

        const volumeSeries = this.volumeSeries[chartId];
        if (volumeSeries) {
            volumeSeries.setData([]);
        }

        this.markers[chartId] = [];
    }

    clearAllCharts() {
        Object.keys(this.charts).forEach(id => this.clearChart(id));
    }
}
