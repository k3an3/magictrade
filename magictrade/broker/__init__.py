from abc import ABC, abstractmethod
from typing import Tuple, Any

import datetime


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
        storage.rpush(self.account_id + ':dates', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        storage.rpush(self.account_id + ':values', self.cash_balance)
