/**
 * OptionScalp Pro - Signals Widget
 */

import { CONFIG } from '../config.js';

export class SignalsWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.signals = [];
    }

    addSignal(signal) {
        // Prevent duplicates
        const sigId = `${signal.strat_name}-${signal.time}-${signal.entry_price}`;
        if (document.getElementById(sigId)) return;

        // Create signal card
        const card = this.createSignalCard(signal, sigId);

        // Add to container (prepend for newest first)
        if (this.container.querySelector('.empty-state')) {
            this.container.innerHTML = '';
        }
        this.container.prepend(card);

        // Limit to MAX_SIGNALS
        while (this.container.children.length > CONFIG.MAX_SIGNALS) {
            this.container.removeChild(this.container.lastChild);
        }

        this.signals.unshift(signal);
    }

    createSignalCard(signal, sigId) {
        const card = document.createElement('div');
        card.id = sigId;
        card.className = 'signal-card slide-in';

        // Determine direction for styling
        const isBullish = !signal.type || !signal.type.includes('PE');
        card.classList.add(isBullish ? 'bullish' : 'bearish');

        // Format time
        const timeStr = signal.time
            ? new Date((signal.time - 19800) * 1000).toLocaleTimeString('en-US', { hour12: false })
            : new Date().toLocaleTimeString('en-US', { hour12: false });

        card.innerHTML = `
            <div class="signal-header">
                <span class="signal-strategy">${signal.strat_name || 'STRATEGY'}</span>
                <span class="signal-time">${timeStr}</span>
            </div>
            <div class="signal-details">
                <div class="signal-detail">
                    <span class="signal-detail-label">Entry</span>
                    <span class="signal-detail-value">₹${signal.entry_price.toFixed(2)}</span>
                </div>
                <div class="signal-detail">
                    <span class="signal-detail-label">Stop Loss</span>
                    <span class="signal-detail-value text-danger">₹${signal.sl ? signal.sl.toFixed(2) : 'N/A'}</span>
                </div>
                <div class="signal-detail">
                    <span class="signal-detail-label">Side</span>
                    <span class="signal-detail-value ${isBullish ? 'text-success' : 'text-danger'}">
                        ${isBullish ? 'CE' : 'PE'}
                    </span>
                </div>
            </div>
            ${signal.reason ? `<div class="signal-reason">${signal.reason}</div>` : ''}
        `;

        return card;
    }

    clear() {
        this.container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📊</div>
                <div class="empty-state-text">No signals yet</div>
            </div>
        `;
        this.signals = [];
    }
}
