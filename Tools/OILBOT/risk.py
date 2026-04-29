import time

class RiskManager:
    def __init__(self, config):
        self.max_trades = config['risk']['max_trades_per_hour']
        self.cooldown = config['risk']['cooldown_seconds']
        self.last_trade_time = 0
        self.trade_count = 0
        self.hour_start = time.time()
        self.max_daily_loss = 0.05  # 5%
        self.daily_pnl = 0

    def can_trade(self):
        now = time.time()

        # Reset hourly count
        if now - self.hour_start > 3600:
            self.trade_count = 0
            self.hour_start = now

        # Cooldown check
        if now - self.last_trade_time < self.cooldown:
            return False

        if self.trade_count >= self.max_trades:
            return False

        if self.daily_pnl < -self.max_daily_loss:
            return False

        return True

    def record_trade(self):
        self.trade_count += 1
        self.last_trade_time = time.time()