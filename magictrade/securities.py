from abc import ABC, abstractmethod
from typing import Dict, List


class InvalidOptionError(Exception):
    """
    Exception to be raised when invalid arguments are provided for an option trade.
    """
    pass


class Option(dict, ABC):
    """
    Base class representing data for a particular options contract.
    """

    def __init__(self, option_data: Dict):
        super().__init__(option_data)
        self.data = option_data

    def __getattr__(self, item):
        if item == 'get':
            return self.data.get

    @property
    @abstractmethod
    def id(self):
        """
        Return the option's unique identifier.
        :return: Broker-provided unique identifier.
        """
        pass

    @property
    @abstractmethod
    def option_type(self) -> str:
        """
        Returns whether the option is a 'call' or 'put'
        :return: 'call' or 'put'
        """
        pass

    @property
    @abstractmethod
    def probability_otm(self) -> float:
        """
        Return the percentage probability that the option will be out-of-the money at expiration.
        :return: Probability OTM
        """
        pass

    @property
    def probability_itm(self) -> float:
        """
        Return the percentage probability that the option will be in-the money at expiration.
        :return: Probability ITM
        """
        return 1 - self.probability_otm

    @property
    @abstractmethod
    def strike_price(self) -> float:
        """
        Return the option's strike price.
        :return: Option strike price
        """
        pass

    @property
    @abstractmethod
    def mark_price(self) -> float:
        """
        Return the option's last trade price.
        :return: Option price
        """
        pass


class OptionOrder(ABC):
    """
    Base class representing data for an option order.
    """

    def __init__(self, order_data: Dict):
        self.data = order_data

    @property
    @abstractmethod
    def id(self) -> str:
        """
        Return the unique id representing the order.
        :return: Order id
        """
        pass

    @property
    @abstractmethod
    def legs(self) -> List[Option]:
        """
        Return a list of options in this order.
        :return: Options in order
        """
        pass


class DummyOption(Option):
    """
    Dummy class for tests.
    """

    def __init__(self, id: str = None, option_type: str = None, probability_otm: float = None,
                 strike_price: float = None, mark_price: float = None):
        self._id = id
        self._option_type = option_type
        self._probability_otm = probability_otm
        self._strike_price = strike_price
        self._mark_price = mark_price

    @property
    def id(self):
        return self._id

    @property
    def option_type(self) -> str:
        return self._option_type

    @property
    def probability_otm(self) -> float:
        return self._probability_otm

    @property
    def strike_price(self) -> float:
        return self._strike_price

    @property
    def mark_price(self) -> float:
        return self._mark_price


class Position(ABC):
    """
    Base class representing data for a stock position.
    """

    def __init__(self, data: Dict):
        self.data = data

    @property
    @abstractmethod
    def quantity(self) -> int:
        pass

    @property
    @abstractmethod
    def symbol(self) -> str:
        pass
