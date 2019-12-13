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


class Option(dict, ABC):
    def __init__(self, option_data: Dict):
        super().__init__(option_data)
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


class OptionOrder(ABC):
    def __init__(self, order_data: Dict):
        self.data = order_data

    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def legs(self):
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
    def date(self) -> datetime:
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
    def options_transact(self, legs: List, direction: str, price: float, quantity: int, effect: str, **kwargs) -> Tuple[
        Any, Any]:
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

    @staticmethod
    def parse_leg(leg: Dict) -> (Dict, str):
        if len(leg) == 2:
            leg, action = leg
        else:
            action = leg['side']
        return leg, action

    @staticmethod
    @abstractmethod
    def leg_in_options(leg: Dict, options: Dict):
        pass
