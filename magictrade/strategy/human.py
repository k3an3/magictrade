from typing import Dict

from magictrade import Broker
from magictrade.strategy import TradingStrategy

DEFAULT_CONFIG = {
    'security_type': 'option',
    'exp_days': '30',
    'strike_dist': 5
}


class HumanTradingStrategy(TradingStrategy):
    def __init__(self, broker: Broker, config: Dict):
        super().__init__(broker)
        self.config = DEFAULT_CONFIG.update(config)

    def make_trade(self, symbol: str):
        pass
