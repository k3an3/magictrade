from logging import getLogger
from math import floor
from typing import Dict

from magictrade import Broker
from magictrade.strategy import TradingStrategy

logger = getLogger('magictrade')


class ReactiveStrategy(TradingStrategy):
    def __init__(self, broker: Broker, config: Dict = {}):
        self.config = config
        self.last_price = 0
        super().__init__(broker)

    def make_trade(self, symbol: str):
        q = self.broker.get_quote(symbol)
        if q >= self.last_price:
            n_shares = floor(self.broker.cash_balance / self.broker.get_quote(symbol))
            self.broker.buy(symbol, n_shares)
            self.last_price = q
            return 'buy', n_shares
        self.last_price = q
        quantity = 0
        try:
            quantity = self.broker.stocks[symbol].quantity
            self.broker.sell(symbol, quantity)
        except KeyError:
            pass
        return 'sell', quantity
