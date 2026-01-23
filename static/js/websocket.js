/**
 * OptionScalp Pro - WebSocket Manager
 */

import { CONFIG } from './config.js';

export class WebSocketManager {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.messageHandlers = new Map();
        this.onConnectionChange = null;
    }

    connect() {
        console.log('Connecting to WebSocket...', CONFIG.WS_URL);

        this.ws = new WebSocket(CONFIG.WS_URL);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.connected = true;
            this.reconnectAttempts = 0;
            if (this.onConnectionChange) {
                this.onConnectionChange(true);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.connected = false;
            if (this.onConnectionChange) {
                this.onConnectionChange(false);
            }
            this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            console.log(`Reconnecting in ${delay}ms... (Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }

    send(data) {
        if (this.connected && this.ws) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('Cannot send message: WebSocket not connected');
        }
    }

    on(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        this.messageHandlers.get(messageType).push(handler);
    }

    handleMessage(data) {
        // Handle pong
        if (data.type === 'ping') {
            this.send({ type: 'pong' });
            return;
        }

        // Call registered handlers
        const handlers = this.messageHandlers.get(data.type);
        if (handlers) {
            handlers.forEach(handler => handler(data));
        }

        // Call wildcard handlers
        const wildcardHandlers = this.messageHandlers.get('*');
        if (wildcardHandlers) {
            wildcardHandlers.forEach(handler => handler(data));
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }
}
