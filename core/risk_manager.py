class RiskManager:
    def __init__(self, daily_loss_limit=2):
        self.daily_loss_limit = daily_loss_limit
        self.losses_today = 0

    def get_sl_tp(self, entry_price, symbol_type="BANKNIFTY"):
        if "BANKNIFTY" in symbol_type:
            sl_pts = 30
        else:
            sl_pts = 20

        return {
            "sl": entry_price - sl_pts,
            "tp1": entry_price + 30,
            "tp2": entry_price + 60,
            "sl_limit": entry_price - sl_pts - 2
        }

    def is_trade_allowed(self):
        return self.losses_today < self.daily_loss_limit
