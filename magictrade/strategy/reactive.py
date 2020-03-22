from logging import getLogger
from math import floor
from typing import Dict, List

from magictrade import Broker
from magictrade.strategy import TradingStrategy
from magictrade.strategy.registry import register_strategy

logger = getLogger('magictrade')


@register_strategy
class ReactiveStrategy(TradingStrategy):
    name = 'reactive'

    def __init__(self, broker: Broker, config: Dict = {}):
        self.config = config
        self.last_price = 0
        super().__init__(broker)

    def make_trade(self, symbol: str):
        q = self.broker.get_quote(symbol)
        if q >= self.last_price:
            n_shares = floor(self.broker.balance / self.broker.get_quote(symbol))
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

    def maintenance(self) -> List:
        pass
