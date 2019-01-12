from abc import ABC, abstractmethod

from magictrade import Broker


class TradingStrategy(ABC):
    def __init__(self, broker: Broker):
        self.broker = broker

    @abstractmethod
    def make_trade(self, symbol: str):
        pass
