import sys
from math import floor
from typing import Dict

from scipy.stats import linregress

from magictrade import Broker, storage
from magictrade.strategy import TradingStrategy

DEFAULT_CONFIG = {
    'security_type': 'stock',
    'exp_days': 30,  # options
    'strike_dist': 5,  # options
    'momentum_slope': 0.20,
    'momentum_window': 10,
    'peak_window': 30,
    'sample_frequency_minutes': 5,
    'stop_loss_percent': 10,
    'take_gain_percent': 20,
    'max_equity': 1_000_000,
}


class HumanTradingStrategy(TradingStrategy):
    def __init__(self, broker: Broker, config: Dict = {}):
        super().__init__(broker)
        self.config = {}
        self.config.update(DEFAULT_CONFIG)
        self.config.update(config)
        self.min = 0
        self.max = 0

    def make_trade(self, symbol: str):
        q = self.broker.get_quote(symbol)
        storage.rpush(symbol, q)
        if self.config['security_type'] == 'option':
            raise NotImplementedError()
        else:
            p = self.broker.stocks.get(symbol)
        # Update min/max values
        if q > self.max:
            self.max = q
        elif q < self.min or self.min == 0:
            self.min = q
        # Already bought, decide whether to sell
        if p:
            chg_since_buy = self.get_percentage_change(p.cost, p.value)
            if chg_since_buy <= -1 * self.config['stop_loss_percent']:
                self.broker.sell(symbol, p.quantity)
            elif chg_since_buy >= self.config['take_gain_percent']:
                # Mark that the minimum gain threshold has been crossed
                p.above_min_gain = True
            elif chg_since_buy < self.config['take_gain_percent'] and p.above_min_gain:
                # We went above a threshold but dropped below it again; sell
                self.broker.sell(symbol, p.quantity)

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

    @staticmethod
    def get_slope(symbol: str) -> float:
        h = [float(s) for s in storage.lrange(symbol, 0, -1)]
        return linregress(range(len(h)), h).slope

    @staticmethod
    def get_slope2(symbol: str) -> float:
        h = [float(s) for s in storage.lrange(symbol, 0, -1)]
        return (h[-1] - h[0]) / len(h)

    @staticmethod
    def get_percentage_change(start: float, end: float) -> float:
        chg = end - start
        return chg / start * 100
