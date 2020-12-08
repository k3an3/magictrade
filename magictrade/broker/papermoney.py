import os
import secrets
import uuid
from datetime import datetime
from typing import Tuple, Dict, List, Any

import requests

from magictrade import Position
from magictrade.broker import Broker, InsufficientFundsError, NonexistentAssetError
from magictrade.broker.registry import register_broker
from magictrade.broker.robinhood import RobinhoodBroker, RHOption, RHOptionOrder
from magictrade.securities import InvalidOptionError
from magictrade.utils import from_date_format, date_format

API_KEY = "3KODWEPB1ZR37OT7"


@register_broker
class PaperMoneyBroker(Broker):
    name = 'papermoney'

    def __init__(self, balance: int = 1_000_000, data: Dict = {}, account_id: str = None,
                 date: str = None, data_files: List[Tuple[str, str]] = [],
                 options_data: Dict = [], exp_dates: Dict = {},
                 buying_power: float = 0.0, broker: Broker = None):
        self._balance = balance
        self.stocks = {}
        self.options = {}
        self.broker = broker
        try:
            self._date = from_date_format(date)
        except Exception:
            self._date = date
        self.data = data
        self.options_data = options_data
        self.exp_dates = exp_dates
        self._buying_power = buying_power
        self._account_id = account_id
        if not data:
            for df in data_files:
                data[df[0]] = {'history': {}}
                d = data[df[0]]['history']
                with open(os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'data', df[1])) as f:
                    for line in f:
                        date, price = line.split(',')
                        d[date] = float(price)
        self._broker = broker
        if self._broker:
            self.option = self._broker.option
        else:
            self._account_id = account_id or secrets.token_urlsafe(6)
            self.option = RHOption

    @property
    def buying_power(self) -> float:
        if self._broker:
            return self._broker.buying_power
        return self._buying_power

    def options_positions(self) -> List:
        if self._broker:
            return self._broker.options_positions()
        if isinstance(self.options, dict):
            return self.options
        else:
            return {option['option']: option for option in self.options}

    def options_positions_data(self, options: List) -> List:
        if self._broker:
            return self._broker.options_positions()
        for option in options:
            for od in self.options_data:
                if option['option'] == od['instrument']:
                    option.data.update(od)
                    break
        return options

    def stock_positions(self) -> List:
        if self._broker:
            return self._broker.stock_positions()

    def get_options(self, symbol: str, actually_work: bool = False) -> List:
        if self._broker:
            return self._broker.get_options(symbol)
        if actually_work:
            return self.options_data[symbol]
        elif self.options_data:
            return self.options_data

    def get_options_data(self, options: List) -> List:
        if self._broker:
            return self._broker.get_options_data(options)
        if self.options_data:
            return self.options_data

    def filter_options(self, options: List, exp_dates: List = [], option_type: str = None):
        if self._broker:
            return self._broker.filter_options(options, exp_dates, option_type)
        if exp_dates:
            return [option for option in options if option["expiration_date"] == exp_dates[0]]
        elif option_type:
            return [RHOption(o) for o in options if o["type"] == option_type]

    def get_value(self) -> float:
        if self._broker:
            return self._broker.get_value()
        value = self.balance
        for equity in self.stocks:
            value += self.stocks[equity].value
        return value

    @property
    def date(self) -> datetime:
        if self._broker:
            return self._broker.date
        return self._date or datetime.now()

    @date.setter
    def date(self, date: str):
        try:
            self._date = from_date_format(date)
        except ValueError:
            self._date = date

    @property
    def account_id(self) -> str:
        if self._broker:
            return self._broker.account_id
        return self._account_id

    def get_quote(self, symbol: str) -> float:
        if self._broker:
            return self._broker.get_quote(symbol)
        if self.data:
            if self._date:
                try:
                    date = from_date_format(self._date)
                except Exception:
                    date = self._date
                # This is terrible but solves some growing pains :/
                try:
                    return self.data[symbol]['history'][date_format(date)]
                except (AttributeError, KeyError):
                    pass
            try:
                return self.data[symbol]['price']
            except KeyError:
                return 0
        else:
            # TODO: use datasource
            data = requests.get('https://www.alphavantage.co/query', params={'function': 'GLOBAL_QUOTE',
                                                                             'symbol': symbol,
                                                                             'apikey': API_KEY
                                                                             }
                                )
            return float(data.json()['Global Quote']['02. open'])

    @property
    def balance(self) -> float:
        if self._broker:
            return self._broker.balance
        return self._balance

    @staticmethod
    def _format_option(symbol: str, expiration: str,
                       strike: float, option_type: str):
        return '{}:{}:{}{}'.format(symbol, expiration, strike,
                                   'c' if option_type == 'call' else 'p')

    def options_transact(self, legs: List[Dict], direction: str, price: float,
                         quantity: int, effect: str = 'open', time_in_force: str = "gfd", **kwargs) -> Tuple[Any, Any]:
        if effect not in ('open', 'close') \
                or direction not in ('credit', 'debit'):
            raise InvalidOptionError()

        if direction == 'debit' and self.balance - price < 0:
            raise InsufficientFundsError()
        self._balance -= price * (-1 if effect == 'close' else 1)
        new_legs = []
        for leg in legs:
            if len(leg) == 2:
                leg, action = leg
            else:
                action = leg['side']
            new_legs.append({
                'side': action,
                'option': leg.get('url') or leg.get('instrument', 'none'),
                'position_effect': effect,
                'ratio_quantity': '1',
                'id': str(uuid.uuid4()),
            })
        return RHOptionOrder({'id': str(uuid.uuid4()), 'legs': new_legs})

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

    def cancel_order(self, ref_id: str):
        raise NotImplementedError

    def replace_order(self, order: str):
        raise NotImplementedError

    def get_order(self, order: str):
        raise NotImplementedError

    def leg_in_options(self, leg: Dict, options: Dict) -> bool:
        if self._broker:
            return self._broker.leg_in_options(leg, options)
        return RobinhoodBroker.leg_in_options(leg, options)
