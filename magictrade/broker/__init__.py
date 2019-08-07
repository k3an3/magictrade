from abc import ABC, abstractmethod

from typing import Tuple, Any, List


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
    def balance(self) -> float:
        pass

    @property
    @abstractmethod
    def buying_power(self) -> float:
        pass

    @abstractmethod
    def get_value(self) -> float:
        pass

    @property
    @abstractmethod
    def date(self) -> str:
        pass

    @abstractmethod
    def options_positions(self) -> List:
        pass

    def options_positions_data(self, options: List) -> List:
        return options

    @abstractmethod
    def get_options(self, symbol: str) -> List:
        pass

    def get_options_data(self, options: List) -> List:
        return options

    @abstractmethod
    def filter_options(self, options: List, exp_dates: List):
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

    @abstractmethod
    def cancel_order(self, ref_id: str):
        pass

    @abstractmethod
    def replace_order(self, order: str):
        pass

    @abstractmethod
    def get_order(self, order: str):
        pass

    def log_balance(self):
        from magictrade import storage
        value = self.get_value()
        storage.rpush(self.account_id + ':dates', self.date.strftime("%Y-%m-%d %H-%M-%S"))
        storage.rpush(self.account_id + ':values', value)
