from typing import Dict

from magictrade.algos import TradingAlgo

DEFAULT_CONFIG = {
    'security_type': 'option',
    'exp_days': '30',
    'strike_dist': 5
}


class HumanTradingAlgo(TradingAlgo):
    def __init__(self, config: Dict):
        self.config = DEFAULT_CONFIG.update(config)

    def make_trade(self, symbol: str):
        pass
