/**
 * OptionScalp Pro - Configuration
 */

export const CONFIG = {
    // WebSocket
    WS_URL: `ws://${window.location.host}/ws`,

    // Chart Settings
    CHART_OPTIONS: {
        layout: {
            background: { type: 'solid', color: '#0B0E11' },
            textColor: '#E0E3EB'
        },
        grid: {
            vertLines: { color: '#1A1B22' },
            horzLines: { color: '#1A1B22' }
        },
        crosshair: {
            mode: 0
        },
        timeScale: {
            borderColor: '#2A2E39',
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 10,
            tickMarkFormatter: (time, tickMarkType, locale) => {
                const date = new Date(time * 1000);
                const h = String(date.getUTCHours()).padStart(2, '0');
                const m = String(date.getUTCMinutes()).padStart(2, '0');
                const s = String(date.getUTCSeconds()).padStart(2, '0');
                return `${h}:${m}:${s}`;
            }
        },
        localization: {
            locale: 'en-IN',
            timeFormatter: (timestamp) => {
                const date = new Date(timestamp * 1000);
                const h = String(date.getUTCHours()).padStart(2, '0');
                const m = String(date.getUTCMinutes()).padStart(2, '0');
                const s = String(date.getUTCSeconds()).padStart(2, '0');
                return `${h}:${m}:${s}`;
            }
        }
    },

    CANDLESTICK_STYLE: {
        upColor: '#26A69A',
        downColor: '#EF5350',
        borderVisible: false,
        wickUpColor: '#26A69A',
        wickDownColor: '#EF5350',
        priceLineVisible: true,
        lastValueVisible: true,
        priceFormat: { type: 'price', precision: 2, minMove: 0.05 }
    },

    VOLUME_STYLE: {
        color: '#26A69A',
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        scaleMargins: { top: 0.85, bottom: 0 }
    },

    // UI Settings
    MAX_SIGNALS: 50,
    SIGNAL_COLORS: {
        TREND_FOLLOWING: '#2196F3',
        DEFAULT: '#FF9800'
    },

    // Update intervals
    UI_UPDATE_THROTTLE: 100 // ms
};
