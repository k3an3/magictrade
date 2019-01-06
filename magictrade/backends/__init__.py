from abc import ABC, abstractmethod
from typing import Tuple, Any


class InsufficientFundsError(Exception):
    pass


class NonexistentAssetError(Exception):
    pass


class InvalidOptionError(Exception):
    pass


class Backend(ABC):
    @abstractmethod
    def get_quote(self, symbol: str, date: str) -> float:
        pass

    @property
    @abstractmethod
    def balance(self) -> float:
        pass

    @abstractmethod
    def options_transact(self, symbol: str, expiration: str, strike: float, quantity: int,
                         option_type: str, action: str) -> Tuple[Any, Any]:
        pass

    @abstractmethod
    def buy(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        pass

    @abstractmethod
    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        pass
