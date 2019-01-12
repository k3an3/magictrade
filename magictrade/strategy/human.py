from math import floor
from typing import Dict

from magictrade import Broker, storage
from magictrade.strategy import TradingStrategy

DEFAULT_CONFIG = {
    'security_type': 'stock',
    'exp_days': 30,  # options
    'strike_dist': 5,  # options
    'momentum_slope': 0.20,
    'momentum_window_samples': 10,
    'sample_frequency_minutes': 5,
    'stop_loss_percent': 10,
    'stop_loss_take_gain_percent': 20,
    'max_equity': 1_000_000,
}


class HumanTradingStrategy(TradingStrategy):
    def __init__(self, broker: Broker, config: Dict = {}):
        super().__init__(broker)
        self.config = {}
        self.config.update(DEFAULT_CONFIG)
        self.config.update(config)

    def make_trade(self, symbol: str):
        q = self.broker.get_quote(symbol)
        storage.rpush(symbol, q)
        if storage.llen(symbol) > self.config['stop_loss_percent']:
            storage.lpop(symbol)
        slope = self.get_slope(symbol)
        # Buy trigger
        if slope >= self.config['momentum_slope']:
            if self.broker.get_value() - self.broker.cash_balance <= self.config['max_equity']:
                self.broker.buy(symbol, floor(min(self.config['max_equity'], self.broker.cash_balance) / q))
                storage.incr('buy')
        # Sell trigger
        elif slope <= self.config['momentum_slope'] * -1:
            p = self.broker.stocks.get(symbol)
            if p:
                self.broker.sell(symbol, p.quantity)
                storage.incr('sell')

    def get_slope(self, symbol: str) -> float:
        h = [float(s) for s in storage.lrange(symbol, 0, -1)]
        return (h[-1] - h[0]) / len(h)
