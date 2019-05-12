import os

import uuid
from datetime import datetime
from typing import Tuple, Dict, List, Any

from fast_arrow import Client, StockMarketdata

from magictrade import Position
from magictrade.broker import Broker, InsufficientFundsError, NonexistentAssetError, InvalidOptionError


class PaperMoneyBroker(Broker):
    def __init__(self, balance: int = 1_000_000, data: Dict = {},
                 account_id: str = None, date: str = None, data_files: List[Tuple[str, str]] = [],
                 options_data: Dict = [],
                 exp_dates: Dict = {}):
        self._balance = balance
        self.stocks = {}
        self.options = {}
        self._date = date
        self.data = data
        self.options_data = options_data
        self.exp_dates = exp_dates
        if not data:
            for df in data_files:
                data[df[0]] = {'history': {}}
                d = data[df[0]]['history']
                with open(os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'data', df[1])) as f:
                    for line in f:
                        date, price = line.split(',')
                        d[date] = float(price)
        self.client = Client()
        self._account_id = account_id

    @property
    def buying_power(self) -> float:
        pass

    def options_positions(self) -> List:
        pass

    def options_positions_data(self, options: List) -> List:
        for option in options:
            for od in self.options_data:
                if 'option' in option and option['option'] == od['instrument']:
                    option.update(od)
        return options

    def get_options(self, symbol: str) -> List:
        return self.options_data

    def get_options_data(self, options: List) -> List:
        return self.options_data

    def filter_options(self, options: List, exp_dates: List):
        pass

    def get_value(self) -> float:
        value = self.balance
        for equity in self.stocks:
            value += self.stocks[equity].value
        return value

    @property
    def date(self) -> str:
        return self._date or datetime.now()

    @date.setter
    def date(self, date: str):
        self._date = date

    @property
    def account_id(self) -> str:
        return self._account_id

    def get_quote(self, symbol: str) -> float:
        if self.data:
            if self._date:
                try:
                    date = datetime.strftime(self._date, "%Y-%m-%d")
                except Exception:
                    date = self._date
                return self.data[symbol]['history'][date]
            return self.data[symbol]['price']
        else:
            return float(StockMarketdata.quote_by_symbol(self.client, symbol)['last_trade_price'])

    @property
    def balance(self) -> float:
        return self._balance

    @staticmethod
    def _format_option(symbol: str, expiration: str,
                       strike: float, option_type: str):
        return '{}:{}:{}{}'.format(symbol, expiration, strike,
                                   'c' if option_type == 'call' else 'p')

    def options_transact(self, legs: List[Dict], symbol: str, direction: str, price: float,
                         quantity: int, effect: str = 'open') -> Tuple[Any, Any]:
        if effect not in ('open', 'close') \
                or direction not in ('credit', 'debit'):
            raise InvalidOptionError()

        if direction == 'debit' and self.balance - price < 0:
            raise InsufficientFundsError()
        self._balance -= price * (-1 if effect == 'close' else 1)
        new_legs = []
        for leg, action, effect in legs:
            new_legs.append({
                'side': action,
                'option': leg['url'],
                'position_effect': effect,
                'ratio_quantity': '1',
                'id': str(uuid.uuid4()),
            })
        return {'id': str(uuid.uuid4()), 'legs': new_legs}

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        debit = self.get_quote(symbol) * quantity
        if self.balance - debit < 0:
            raise InsufficientFundsError()
        self._balance -= debit
        if self.stocks.get(symbol):
            self.stocks[symbol].quantity += quantity
            self.stocks[symbol].cost += quantity
        else:
            self.stocks[symbol] = Position(str(uuid.uuid4()), symbol, debit, quantity, self)
        return 'success', self.stocks[symbol]

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        position = self.stocks.get(symbol)
        if not position or position.quantity < quantity:
            raise NonexistentAssetError()
        credit = self.get_quote(symbol) * quantity
        self._balance += credit
        position.quantity -= quantity
        position.cost -= credit
        if position.quantity == 0:
            del self.stocks[symbol]
            position = None
        return 'success', position
