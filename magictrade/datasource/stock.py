import datetime
from typing import List

import requests

from magictrade import storage
from magictrade.datasource import DataSource
from magictrade.utils import date_format

FINNHUB_URL = 'https://finnhub.io/api/v1/'
# TODO: put in settings, revoke token
FINNHUB_TOKEN = 'os.environ['FINNHUB_TOKEN']'


class Cache:
    def __init__(self):
        self.prefix = "finnhub_cache:"

    def get(self, symbol: str, days: int) -> List[float]:
        if storage.get(f"{self.prefix}{symbol}:{days}:current") == date_format(datetime.datetime.now()):
            return [float(v) for v in storage.lrange(f"{self.prefix}{symbol}:{days}", 0, -1)]
        return []

    def save(self, symbol: str, days: int, data: List[float]):
        storage.lpush(f"{self.prefix}{symbol}:{days}", *data)
        storage.set(f"{self.prefix}{symbol}:{days}:current", date_format(datetime.datetime.now()))


# TODO
cache = Cache()


class FinnhubDataSource(DataSource):
    @staticmethod
    def get_quote(symbol: str) -> float:
        r = requests.get(FINNHUB_URL + 'quote', params={'symbol': symbol, 'token': FINNHUB_TOKEN})
        return float(r.json()['c'])

    @staticmethod
    def get_historic_close(symbol: str, days: int) -> List[float]:
        if data := cache.get(symbol, days):
            return data
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=days)
        r = requests.get(FINNHUB_URL + 'stock/candle', params={
            'symbol': symbol,
            'resolution': 'D',
            'from': round(start.timestamp()),
            'to': round(end.timestamp()),
            'token': FINNHUB_TOKEN,
        })
        data = r.json()
        try:
            data = data['c']
        except KeyError:
            # TODO: better
            return []
        cache.save(symbol, days, data)
        if isinstance(data[0], str):
            data = [float(v) for v in data]
        return data
