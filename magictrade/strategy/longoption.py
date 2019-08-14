from datetime import timedelta, datetime
from typing import List, Dict

from magictrade import Broker, storage
from magictrade.strategy import TradingStrategy
from magictrade.utils import get_percentage_change, get_allocation

strategies = {
}

total_allocation = 40
option_types = ('call', 'put')


class LongOptionTradingStrategy(TradingStrategy):
    name = 'longoption'

    def __init__(self, broker: Broker):
        self.broker = broker

    @staticmethod
    def _get_quantity(allocation: float, spread_width: float) -> int:
        return int(allocation / (spread_width * 100))


    @staticmethod
    def check_positions(legs: List, options: Dict) -> Dict:
        for leg in legs:
            if not leg['option'] in options:
                return leg

    @staticmethod
    def invert_action(legs: List) -> None:
        for leg in legs:
            if leg['side'] == 'buy':
                leg['side'] = 'sell'
            else:
                leg['side'] = 'buy'

    def maintenance(self) -> List:
        pass


    def make_trade(self, symbol: str, option_type: str, expiration_date: str, allocation_percent: int = 3, allocation_dollars: int = 0):
        pass