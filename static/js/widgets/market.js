/**
 * OptionScalp Pro - Market Overview Widget
 */

export class MarketOverviewWidget {
    constructor() {
        this.elements = {
            indexPrice: document.getElementById('index-price'),
            indexChange: document.getElementById('index-change'),
            trend: document.getElementById('market-trend'),
            pcrValue: document.getElementById('pcr-value'),
            pcrStatus: document.getElementById('pcr-status')
        };
    }

    updateIndexPrice(price, change = null) {
        if (this.elements.indexPrice) {
            this.elements.indexPrice.textContent = price ? price.toFixed(2) : '--';
        }

        if (change !== null && this.elements.indexChange) {
            const changePercent = ((change / price) * 100).toFixed(2);
            const isPositive = change >= 0;

            this.elements.indexChange.innerHTML = `
                <span class="${isPositive ? 'text-success' : 'text-danger'}">
                    ${isPositive ? '▲' : '▼'} ${Math.abs(changePercent)}%
                </span>
            `;

            this.elements.indexChange.className = `metric-change ${isPositive ? 'up' : 'down'}`;
        }
    }

    updateTrend(trend) {
        if (this.elements.trend) {
            this.elements.trend.textContent = trend || '--';

            // Color coding
            const trendLower = (trend || '').toLowerCase();
            if (trendLower.includes('bull')) {
                this.elements.trend.className = 'metric-value text-success';
            } else if (trendLower.includes('bear')) {
                this.elements.trend.className = 'metric-value text-danger';
            } else {
                this.elements.trend.className = 'metric-value';
            }
        }
    }

    updatePCR(pcrData) {
        if (!pcrData) return;

        // Update PCR value
        if (this.elements.pcrValue) {
            const pcr = pcrData.pcr || pcrData;
            this.elements.pcrValue.textContent = typeof pcr === 'number' ? pcr.toFixed(2) : pcr;
        }

        // Update buildup status
        if (this.elements.pcrStatus && pcrData.buildup_status) {
            const status = pcrData.buildup_status;
            this.elements.pcrStatus.textContent = status;

            // Update badge color
            this.elements.pcrStatus.className = 'badge';
            if (status.includes('LONG BUILD')) {
                this.elements.pcrStatus.classList.add('badge-success');
            } else if (status.includes('SHORT BUILD')) {
                this.elements.pcrStatus.classList.add('badge-danger');
            } else if (status.includes('SHORT COVER')) {
                this.elements.pcrStatus.classList.add('badge-info');
            } else {
                this.elements.pcrStatus.classList.add('badge-neutral');
            }
        }
    }

    reset() {
        if (this.elements.indexPrice) this.elements.indexPrice.textContent = '--';
        if (this.elements.indexChange) this.elements.indexChange.innerHTML = '<span>--</span>';
        if (this.elements.trend) this.elements.trend.textContent = '--';
        if (this.elements.pcrValue) this.elements.pcrValue.textContent = '--';
        if (this.elements.pcrStatus) {
            this.elements.pcrStatus.textContent = '--';
            this.elements.pcrStatus.className = 'badge badge-neutral';
        }
    }
}
