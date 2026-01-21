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
        self.total_pnl = 0
        self.win_count = 0
        self.loss_count = 0

    def add_trade(self, trade):
        self.trades.append(trade)

    def update_stats(self):
        # Recalculate from closed trades
        self.total_pnl = 0
        self.win_count = 0
        self.loss_count = 0
        for t in self.trades:
            if t.status == 'CLOSED':
                self.total_pnl += t.pnl
                if t.pnl > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1

    def get_stats(self):
        self.update_stats()
        closed_trades = [t for t in self.trades if t.status == 'CLOSED']
        total_closed = len(closed_trades)
        win_rate = (self.win_count / total_closed * 100) if total_closed > 0 else 0
        return {
            "total_trades": len(self.trades),
            "total_closed": total_closed,
            "total_pnl": round(self.total_pnl, 2),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(win_rate, 2)
        }
