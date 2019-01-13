import os
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

    def log_balance(self, date: str = None):
        from magictrade import storage
        date = date or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        value = self.get_value()
        storage.rpush(self.account_id + ':dates', date)
        storage.rpush(self.account_id + ':values', value)
        filename = self.account_id + ".log"
        with open(os.path.join('logs', filename), 'a' if os.path.exists(filename) else 'w') as f:
            f.write("{},{}\n".format(date, value))
