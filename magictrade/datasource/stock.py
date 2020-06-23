import datetime
from typing import List

import requests

from magictrade import storage
from magictrade.utils import date_format

FINNHUB_URL = 'https://finnhub.io/api/v1/'
FINNHUB_TOKEN = 'os.environ['FINNHUB_TOKEN']'


class Cache:
    def __init__(self):
        self.prefix = "finnhub_cache:"

    def get(self, symbol: str, days: int) -> List[float]:
        if storage.get(f"{self.prefix}{symbol}:{days}:current") == date_format(datetime.datetime.now()):
            return storage.lrange(f"{self.prefix}{symbol}:{days}")
        return []

    def save(self, symbol: str, days: int, data: List[float]):
        storage.lpush(f"{self.prefix}{symbol}:{days}", *data)
        storage.set(f"{self.prefix}{symbol}:{days}:current", date_format(datetime.datetime.now()))


# TODO
cache = Cache()


def get_historic_close(symbol: str, days: int) -> List[float]:
    """
    Use Finnhub APIs to retrieve historic close values for the provided ticker. Retrieved data is saved to a cache for the day.
    :param symbol: Ticker symbol to look up.
    :param days: Number of days to look back.
    :return: A list of close prices.
    """
    if data := cache.get(symbol, days):
        return data
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=days)
    r = requests.get(FINNHUB_URL + 'stock/candle', params={
        'symbol': symbol,
        'resolution': 'D',
        'from': start.timestamp(),
        'to': end.timestamp(),
        'token': FINNHUB_TOKEN,
    })
    data = r.json()['c']
    cache.set(symbol, days, data)
    return data
