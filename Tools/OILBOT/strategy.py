class Strategy:
    def __init__(self, config):
        self.threshold = config['strategy']['spike_threshold']
        self.imbalance_th = config['strategy']['imbalance_threshold']

        self.last_price = None

    def generate_signal(self, price, imbalance, news_signal):
        if self.last_price is None:
            self.last_price = price
            return "NO_TRADE"

        change = (price - self.last_price) / self.last_price

        self.last_price = price

        # Spike detection
        if abs(change) < self.threshold:
            return "NO_TRADE"

        # Combine signals
        if change > 0:
            if imbalance > self.imbalance_th and news_signal == "BULLISH":
                return "LONG"
            elif imbalance < -self.imbalance_th:
                return "SHORT"

        if change < 0:
            if imbalance < -self.imbalance_th and news_signal == "BEARISH":
                return "SHORT"
            elif imbalance > self.imbalance_th:
                return "LONG"

        return "NO_TRADE"

class MLStrategy:
    def __init__(self, model):
        self.model = model

    def predict(self, features_row):
        pred = self.model.predict([features_row])[0]

        if pred == 1:
            return "LONG"
        elif pred == -1:
            return "SHORT"
        return "NO_TRADE"