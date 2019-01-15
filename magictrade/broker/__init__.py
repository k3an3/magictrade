import os
from abc import ABC, abstractmethod
from typing import Tuple, Any


class InsufficientFundsError(Exception):
    pass


class NonexistentAssetError(Exception):
    pass


class InvalidOptionError(Exception):
    pass


class Broker(ABC):
    @abstractmethod
    def get_quote(self, symbol: str) -> float:
        pass

    @property
    @abstractmethod
    def account_id(self) -> str:
        pass

    @property
    @abstractmethod
    def cash_balance(self) -> float:
        pass

    @abstractmethod
    def get_value(self) -> float:
        pass

    @property
    @abstractmethod
    def date(self) -> str:
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

    def log_balance(self):
        from magictrade import storage
        value = self.get_value()
        storage.rpush(self.account_id + ':dates', self.date)
        storage.rpush(self.account_id + ':values', value)
