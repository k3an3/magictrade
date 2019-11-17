from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple, Any, List, Dict

from magictrade.broker.registry import brokers


def load_brokers():
    from magictrade.utils import import_modules
    import_modules(__file__, 'broker')


class InsufficientFundsError(Exception):
    pass


class NonexistentAssetError(Exception):
    pass


class InvalidOptionError(Exception):
    pass


class Option(ABC):
    def __init__(self, option_data: Dict):
        self.data = option_data

    def __getattr__(self, item):
        if item == 'get':
            return self.data.get

    @property
    @abstractmethod
    def id(self):
        pass

    @property
    @abstractmethod
    def option_type(self) -> str:
        pass

    @property
    @abstractmethod
    def probability_otm(self) -> float:
        pass

    @property
    @abstractmethod
    def strike_price(self) -> float:
        pass

    @property
    @abstractmethod
    def mark_price(self) -> float:
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
    def date(self) -> str:
        return datetime.now()

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
    def filter_options(self, options: List, exp_dates: List, option_type: str = None) -> List[Option]:
        pass

    @abstractmethod
    def options_transact(self, legs: List, direction: str, price: float, quantity: int, effect: str) -> Tuple[Any, Any]:
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
        storage.rpush(self.account_id + ':dates', self.date.strftime("%Y-%m-%d %H-%M-%S"))
        storage.rpush(self.account_id + ':values', value)
