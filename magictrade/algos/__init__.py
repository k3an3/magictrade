from abc import ABC, abstractmethod


class TradingAlgo(ABC):
    @abstractmethod
    def make_trade(self, symbol: str, config):
        pass
