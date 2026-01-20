class RiskManager:
    def __init__(self, daily_loss_limit=2):
        self.daily_loss_limit = daily_loss_limit
        self.trades_today = 0
        self.losses_today = 0
        self.stopped_for_day = False

    def reset_daily_stats(self):
        self.trades_today = 0
        self.losses_today = 0
        self.stopped_for_day = False

    def check_trade_allowed(self):
        if self.stopped_for_day:
            return False
        if self.losses_today >= self.daily_loss_limit:
            self.stopped_for_day = True
            return False
        return True

    def record_trade_result(self, is_win):
        self.trades_today += 1
        if not is_win:
            self.losses_today += 1

        if self.losses_today >= self.daily_loss_limit:
            self.stopped_for_day = True

    def get_sl_tp(self, entry_price, symbol_type="BANKNIFTY", side="BUY"):
        # For Bank Nifty: 30 pts SL, R1=30, R2=60
        # For Nifty: 15-20 pts SL
        if "BANKNIFTY" in symbol_type:
            sl_points = 30
            r1_points = 30
            r2_points = 60
        else:
            sl_points = 20
            r1_points = 20
            r2_points = 40

        if side == "BUY":
            sl = entry_price - sl_points
            tp1 = entry_price + r1_points
            tp2 = entry_price + r2_points
        else: # SELL
            sl = entry_price + sl_points
            tp1 = entry_price - r1_points
            tp2 = entry_price - r2_points

        return {"sl": sl, "tp1": tp1, "tp2": tp2, "sl_limit": sl - 2 if side == "BUY" else sl + 2}
