from abc import ABC, abstractmethod


class TradingStrategy(ABC):
    @abstractmethod
    def make_trade(self, symbol: str, config):
        pass
