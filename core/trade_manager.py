from datetime import datetime

class Trade:
    def __init__(self, symbol, entry_price, entry_time, trade_type, strategy_name, sl=None, target=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.trade_type = trade_type # 'LONG' or 'SHORT' (Signals market direction)
        self.strategy_name = strategy_name
        self.sl = sl
        self.target = target

        self.exit_price = None
        self.exit_time = None
        self.status = 'OPEN' # 'OPEN', 'CLOSED'
        self.pnl = 0
        self.exit_reason = None # 'SL', 'TARGET', 'TIME'

    def close(self, exit_price, exit_time, reason):
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.status = 'CLOSED'
        self.exit_reason = reason

        # PnL Calculation: We are ALWAYS BUYING options in this system.
        # Whether it's a Call (Market Long) or Put (Market Short),
        # profit is made if the premium RISES.
        self.pnl = self.exit_price - self.entry_price

class PnLTracker:
    def __init__(self):
        self.trades = []
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.max_drawdown = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.unrealized_pnl = 0.0
        self.net_total_pnl = 0.0

    def add_trade(self, trade):
        self.trades.append(trade)

    def update_stats(self, active_trades=None, current_prices=None):
        # Recalculate from closed trades
        self.total_pnl = 0
        self.win_count = 0
        self.loss_count = 0
        
        total_win = 0
        total_loss = 0
        peak = 0
        max_dd = 0
        current_pnl = 0

        # 1. Process Closed Trades
        for t in self.trades:
            if t.status == 'CLOSED':
                self.total_pnl += t.pnl
                current_pnl += t.pnl
                
                # Drawdown Logic
                if current_pnl > peak:
                    peak = current_pnl
                dd = peak - current_pnl
                if dd > max_dd: max_dd = dd

                if t.pnl > 0:
                    self.win_count += 1
                    total_win += t.pnl
                else:
                    self.loss_count += 1
                    total_loss += abs(t.pnl)

        # 2. Process Active Trades (Unrealized PnL)
        self.unrealized_pnl = 0
        if active_trades and current_prices:
            for t in active_trades:
                if t.symbol in current_prices:
                    curr_price = current_prices[t.symbol]
                    # We always BUY options (Long Volatility)
                    # PnL = (Current Price - Entry Price)
                    unrealized = curr_price - t.entry_price
                    self.unrealized_pnl += unrealized
                    
                    # Update peak/dd logic tentatively for running drawdown
                    # (Optional: might be too noisy, but accurate for "Total PnL")
        
        self.net_total_pnl = self.total_pnl + self.unrealized_pnl
        
        self.max_drawdown = max_dd
        self.avg_win = total_win / self.win_count if self.win_count > 0 else 0
        self.avg_loss = total_loss / self.loss_count if self.loss_count > 0 else 0

    def get_stats(self):
        # Note: update_stats should be called before this with live data if needed
        closed_trades = [t for t in self.trades if t.status == 'CLOSED']
        total_closed = len(closed_trades)
        win_rate = (self.win_count / total_closed * 100) if total_closed > 0 else 0
        return {
            "total_trades": len(self.trades),
            "total_closed": total_closed,
            "total_pnl": round(self.net_total_pnl if hasattr(self, 'net_total_pnl') else self.total_pnl, 2),
            "realized_pnl": round(self.total_pnl, 2),
            "unrealized_pnl": round(getattr(self, 'unrealized_pnl', 0), 2),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(win_rate, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2)
        }
