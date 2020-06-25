from abc import abstractmethod, ABC
from typing import List


class DataSource(ABC):
    @abstractmethod
    def get_historic_close(self, symbol: str, days: int) -> List[float]:
        """
        Retrieve historic close values for the provided ticker.
        :param symbol: Ticker symbol to look up.
        :param days: Number of days to look back.
        :return: A list of close prices.
        """
        pass


class DummyDataSource(DataSource, dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_historic_close(self, symbol: str, days: int):
        return self['history'][symbol][days * -1:]
