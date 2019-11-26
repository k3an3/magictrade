from math import floor
from typing import Dict

try:
    from scipy.stats import linregress
except ImportError:
    pass

from magictrade import Broker, storage, Position
from magictrade.strategy import TradingStrategy
from magictrade.strategy.registry import register_strategy
from magictrade.utils import get_percentage_change

DEFAULT_CONFIG = {
    'security_type': 'stock',
    'exp_days': 30,  # options
    'strike_dist': 5,  # options
    'momentum_slope': 0.20,
    'momentum_window': 10,
    'peak_window': 30,
    'peak_pullback_pct': 10,
    'sample_frequency_minutes': 5,
    'stop_loss_pct': 10,
    'take_gain_pct': 20,
    'max_equity': 1_000_000,
    'short_window': 5,
    'med_window': 10,
    'long_window': 20,
}


@register_strategy
class HumanTradingStrategy(TradingStrategy):
    name = 'human'

    def __init__(self, broker: Broker, config: Dict = {}):
        super().__init__(broker)
        self.config = {**DEFAULT_CONFIG, **config}
        self.trades = {}

    def _buy(self, symbol: str, quantity: int, reason: str = None):
        self.broker.buy(symbol, quantity)
        self._transact(symbol, quantity, 'buy', reason)

    def _sell(self, symbol: str, quantity: int, reason: str = None):
        self.broker.sell(symbol, quantity)
        self._transact(symbol, quantity, 'sell', reason)

    def _transact(self, symbol: str, quantity: int, action: str, reason: str = None):
        self.trades[self.broker.date] = (action, symbol, quantity, reason)
        storage.incr(action)

    def _should_buy(self, symbol: str, q: float):
        for win in ('short', 'med', 'long'):
            if self._get_window_change(symbol, win) >= self.config['{}_window_pct'.format(win)]:
                self._buy(symbol, self._get_quantity(q), "{} window met".format(win))
                break

    def _should_sell(self, p: Position):
        # Mark that the minimum gain threshold has been crossed
        chg_since_buy = get_percentage_change(p.cost, p.value)
        # Mark that the minimum gain threshold has been crossed
        if chg_since_buy >= self.config['take_gain_pct']:
            p.data['above_min_gain'] = True
        if chg_since_buy <= -1 * self.config['stop_loss_pct']:
            self._sell(p.symbol, p.quantity, "stop loss")
        elif chg_since_buy < self.config['take_gain_pct'] and p.data.get('above_min_gain'):
            # We went above a threshold but dropped below it again; sell
            self._sell(p.symbol, p.quantity, "take min gain")
        else:
            for win in ('short', 'med', 'long'):
                wc = self._get_window_change(p.symbol, win)
                if wc < self.config['{}_window_pct'.format(win)] * -1 < 0:
                    self._sell(p.symbol, p.quantity, "take gain off peak")

    def make_trade(self, symbol: str):
        q = self.broker.get_quote(symbol)
        storage.rpush(symbol, q)
        if self.config['security_type'] == 'option':
            raise NotImplementedError()
        else:
            p = self.broker.stocks.get(symbol)
        # Already bought, decide whether to sell
        if p:
            # Update min/max values
            if q > p.data.get('max', 0):
                p.data['max'] = q
            elif not p.data.get('min') or q < p.data.get('min'):
                p.data['min'] = q
            self._should_sell(p)
        # Haven't bought, may need to
        else:
            self._should_buy(symbol, q)

    def _get_quantity(self, q: float):
        return floor(min(self.config['max_equity'], self.broker.balance) / q)

    @staticmethod
    def get_slope(symbol: str) -> float:
        h = [float(s) for s in storage.lrange(symbol, 0, -1)]
        return linregress(range(len(h)), h).slope

    @staticmethod
    def get_slope2(symbol: str) -> float:
        h = [float(s) for s in storage.lrange(symbol, 0, -1)]
        return (h[-1] - h[0]) / len(h)

    def _get_window_change(self, symbol: str, win: str) -> float:
        start = self.config['{}_window'.format(win)]
        if storage.llen(symbol) < start:
            start = 0
        r = [float(n) for n in storage.lrange(symbol, -1 * start, -1)]
        if r:
            return get_percentage_change(r[0], r[-1])
        return 0.0

