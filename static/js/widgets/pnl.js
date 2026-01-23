/**
 * OptionScalp Pro - PnL Widget
 */

export class PnLWidget {
    constructor() {
        this.elements = {
            mainValue: document.getElementById('pnl-main-value'),
            closed: document.getElementById('pnl-closed'),
            open: document.getElementById('pnl-open'),
            wins: document.getElementById('pnl-wins'),
            losses: document.getElementById('pnl-losses'),
            winRateFill: document.getElementById('win-rate-fill'),
            winRateText: document.getElementById('win-rate-text')
        };
    }

    update(stats) {
        if (!stats) {
            this.reset();
            return;
        }

        // Update main PnL value
        const pnl = stats.total_pnl || 0;
        this.elements.mainValue.textContent = `₹${pnl.toFixed(2)}`;

        // Update color
        this.elements.mainValue.classList.remove('positive', 'negative');
        if (pnl > 0) {
            this.elements.mainValue.classList.add('positive');
        } else if (pnl < 0) {
            this.elements.mainValue.classList.add('negative');
        }

        // Update stats
        this.elements.closed.textContent = stats.total_closed || 0;
        this.elements.open.textContent = (stats.total_trades - stats.total_closed) || 0;
        this.elements.wins.textContent = stats.win_count || 0;
        this.elements.losses.textContent = stats.loss_count || 0;

        // Update win rate
        const winRate = stats.win_rate || 0;
        this.elements.winRateFill.style.width = `${winRate}%`;
        this.elements.winRateText.textContent = `Win Rate: ${winRate}%`;
    }

    reset() {
        this.elements.mainValue.textContent = '₹0.00';
        this.elements.mainValue.classList.remove('positive', 'negative');
        this.elements.closed.textContent = '0';
        this.elements.open.textContent = '0';
        this.elements.wins.textContent = '0';
        this.elements.losses.textContent = '0';
        this.elements.winRateFill.style.width = '0%';
        this.elements.winRateText.textContent = 'Win Rate: 0%';
    }
}
