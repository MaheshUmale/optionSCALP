/**
 * OptionScalp Pro - Strategy Performance Widget
 */

export class StrategyWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
    }

    update(report) {
        if (!report || Object.keys(report).length === 0) {
            this.showEmpty();
            return;
        }

        this.container.innerHTML = '';

        // Sort strategies by PnL
        const strategies = Object.entries(report)
            .sort(([, a], [, b]) => b.pnl - a.pnl);

        strategies.forEach(([name, stats]) => {
            const item = this.createStrategyItem(name, stats);
            this.container.appendChild(item);
        });
    }

    createStrategyItem(name, stats) {
        const item = document.createElement('div');
        item.className = 'strategy-item';

        const isPositive = stats.pnl >= 0;

        item.innerHTML = `
            <div class="strategy-info">
                <div class="strategy-name">${name}</div>
                <div class="strategy-stats">
                    <span>${stats.total} trades</span>
                    <span>Win Rate: ${stats.win_rate}%</span>
                </div>
            </div>
            <div class="strategy-pnl ${isPositive ? 'positive' : 'negative'}">
                ₹${stats.pnl.toFixed(2)}
            </div>
        `;

        return item;
    }

    showEmpty() {
        this.container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚡</div>
                <div class="empty-state-text">No strategy data yet</div>
            </div>
        `;
    }
}
