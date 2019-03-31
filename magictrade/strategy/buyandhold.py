from logging import getLogger
from math import floor
from typing import Dict

from magictrade import Broker
from magictrade.broker import InsufficientFundsError
from magictrade.strategy import TradingStrategy

logger = getLogger('magictrade')


class BuyandHoldStrategy(TradingStrategy):
    def __init__(self, broker: Broker, config: Dict = {}):
        self.config = config
        super().__init__(broker)

    def make_trade(self, symbol: str):
        n_shares = floor(self.broker.balance / self.broker.get_quote(symbol))
        while n_shares > 0:
            try:
                result = self.broker.buy(symbol, n_shares)
                n_shares = 0
            except InsufficientFundsError:
                logger.warning("BuyandHold: Insufficient funds for purchase. Decreasing share count to %d", n_shares)
                n_shares -= 1
            else:
                pos = result[1]
                logger.info("BuyandHold: Purchased {} shares for {} with result {}".format(pos.quantity, pos.cost, result[0]))
                return result
        return False


