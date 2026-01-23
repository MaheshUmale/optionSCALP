/**
 * OptionScalp Pro - Chart Manager
 */

import { CONFIG } from '../config.js';

export class ChartManager {
    constructor() {
        this.charts = {};
        this.series = {};
        this.volumeSeries = {};
        this.chartElements = {};
        this.storedData = {
            index: [],
            ce: [],
            pe: []
        };
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

        // Initial resize
        setTimeout(() => this.handleResize(), 200);
    }

    createChart(id, elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error(`Chart element ${elementId} not found`);
            return;
        }

        // Store element for resizing
        this.chartElements[id] = element;

        // Create chart instance
        const chart = LightweightCharts.createChart(element, {
            ...CONFIG.CHART_OPTIONS,
            width: element.clientWidth || 300,
            height: element.clientHeight || 300
        });

        // Add candlestick series
        const candleSeries = chart.addCandlestickSeries({
            ...CONFIG.CANDLESTICK_STYLE,
            priceScaleId: 'right'
        });

        // Configure price scale with better margins to prevent excessive zoom
        chart.priceScale('right').applyOptions({
            autoScale: true,
            borderVisible: false,
            scaleMargins: { top: 0.08, bottom: 0.08 },  // Moderate margins to balance zoom vs visibility
            minimumWidth: 80,
            alignLabels: true
        });

        // Add volume series
        const volumeSeries = chart.addHistogramSeries(CONFIG.VOLUME_STYLE);

        // Configure volume scale explicitly
        chart.priceScale('volume').applyOptions({
            scaleMargins: CONFIG.VOLUME_STYLE.scaleMargins,
            borderVisible: false,
            alignLabels: false
        });

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

        if (!series || !data || data.length === 0) return;

        const candleData = data.filter(d => d.open > 0 && d.high > 0 && d.low > 0 && d.close > 0).map(d => ({
            time: d.time,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close
        }));

        const volumeData = data.filter(d => d.open > 0).map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? '#26A69A' : '#EF5350'
        }));

        series.setData(candleData);
        if (volumeSeries) {
            volumeSeries.setData(volumeData);
        }

        // Store data for alignment/referencing
        const isInitialLoad = !this.storedData[chartId] || this.storedData[chartId].length === 0;
        this.storedData[chartId] = candleData;

        // Scaling logic: 
        // 1. On first load, fit content.
        // 2. On subsequent updates (replay), maintain a fixed zoom window (e.g., 60 bars)
        //    that follows the leading edge (the "live" candle).
        if (isInitialLoad) {
            this.charts[chartId].timeScale().fitContent();
        } else {
            // Smoothly track the leading edge
            const chart = this.charts[chartId];
            const lastCandle = candleData[candleData.length - 1];

            // We want to see roughly 60 candles. 
            // Lightweight charts works by logical index or time.
            // Since we use setData with full slice, logical indices are reset.
            // Let's use visible range based on time for stability.
            const barsToShow = 60;
            const startIndex = Math.max(0, candleData.length - barsToShow);

            chart.timeScale().setVisibleRange({
                from: candleData[startIndex].time,
                to: lastCandle.time + (60 * 5) // Add 5 mins buffer on right
            });
        }
    }

    updateLiveCandle(chartId, candle) {
        const series = this.series[chartId];
        const volumeSeries = this.volumeSeries[chartId];

        if (!series) return;

        // Ensure we don't send back-dated candles (prevents "Cannot update oldest data" crash)
        if (this.storedData[chartId] && this.storedData[chartId].length > 0) {
            const lastCandle = this.storedData[chartId][this.storedData[chartId].length - 1];

            if (candle.time < lastCandle.time) {
                // If the drift is significant (> 1s), log it and ignore.
                if (lastCandle.time - candle.time > 1) {
                    console.warn(`[${chartId}] Ignoring back-dated candle: last=${lastCandle.time}, new=${candle.time}, diff=${lastCandle.time - candle.time}s`);
                    return;
                }
                // Else it's likely a sub-second tick or the same second, which series.update handles fine as long as not older than prior-to-last.
            }

            if (candle.time > lastCandle.time) {
                this.storedData[chartId].push({ ...candle });
                if (this.storedData[chartId].length > 1000) this.storedData[chartId].shift();
            } else if (candle.time === lastCandle.time) {
                Object.assign(lastCandle, candle);
            }
        } else {
            this.storedData[chartId] = [{ ...candle }];
        }

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
            chart.timeScale().fitContent();
        }
    }

    alignCharts(bars = 50) {
        // Find the chart with the most recent data to use as anchor
        if (!this.storedData || !this.storedData['index']) return;
        const data = this.storedData['index'];
        if (data.length === 0) return;

        // Calculate range
        const lastIndex = data.length - 1;
        const startIndex = Math.max(0, lastIndex - bars);

        const fromTime = data[startIndex].time;
        const toTime = data[lastIndex].time;

        const range = { from: fromTime, to: toTime };

        // Apply to ALL charts
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.timeScale().setVisibleRange(range);
            }
        });
    }

    handleResize() {
        Object.entries(this.charts).forEach(([id, chart]) => {
            const element = this.chartElements[id];
            if (element) {
                const w = element.clientWidth;
                const h = element.clientHeight;
                if (w > 0 && h > 0) {
                    chart.resize(w, h);
                }
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
