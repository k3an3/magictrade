from abc import ABC, abstractmethod
from typing import Tuple

from magictrade import Position


class Backend(ABC):
    @abstractmethod
    def get_quote(self, symbol) -> float:
        pass

    @property
    @abstractmethod
    def balance(self) -> float:
        pass

    @abstractmethod
    def options_transact(self, symbol: str, expiration: str, strike: float, quantity: int, mode: str, direction: str) -> Tuple[str, Position]:
        pass

    @abstractmethod
    def buy(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        pass

    @abstractmethod
    def sell(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        pass
