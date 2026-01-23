/**
 * OptionScalp Pro - Active Positions Widget
 */

export class PositionsWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.countElement = document.getElementById('positions-count');
    }

    update(positions) {
        if (!positions || positions.length === 0) {
            this.showEmpty();
            this.updateCount(0);
            return;
        }

        this.container.innerHTML = '';
        this.updateCount(positions.length);

        positions.forEach(pos => {
            const item = this.createPositionItem(pos);
            this.container.appendChild(item);
        });
    }

    updateCount(count) {
        if (this.countElement) {
            this.countElement.textContent = `${count} position${count !== 1 ? 's' : ''}`;
        }
    }

    createPositionItem(pos) {
        const item = document.createElement('div');
        item.className = 'position-item';

        // Calculate PnL if not provided
        let pnl = pos.pnl;
        if (typeof pnl !== 'number' && pos.current_price && pos.entry_price) {
            pnl = (pos.current_price - pos.entry_price) * (pos.quantity || 1);
        }

        const isPositive = pnl >= 0;
        const pnlClass = isPositive ? 'text-success' : 'text-danger';
        const pnlSign = isPositive ? '+' : '';

        item.innerHTML = `
            <div class="position-header">
                <span class="position-symbol">${pos.symbol.replace('NSE:', '')}</span>
                <span class="position-strategy badge badge-neutral">${pos.strategy || 'MANUAL'}</span>
            </div>
            <div class="position-details">
                <div class="position-row">
                    <span class="label">Entry</span>
                    <span class="value">₹${pos.entry_price.toFixed(2)}</span>
                </div>
                <div class="position-row">
                    <span class="label">LTP</span>
                    <span class="value">₹${pos.current_price.toFixed(2)}</span>
                </div>
            </div>
            <div class="position-pnl ${pnlClass}">
                ${pnlSign}₹${pnl.toFixed(2)}
            </div>
        `;

        return item;
    }

    showEmpty() {
        this.container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <div class="empty-state-text">No active positions</div>
            </div>
        `;
    }
}
