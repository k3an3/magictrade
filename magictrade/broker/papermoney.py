import os
import uuid
from datetime import datetime
from typing import Tuple, Dict, List, Any

import requests

from magictrade import Position
from magictrade.broker import Broker, InsufficientFundsError, NonexistentAssetError, InvalidOptionError
from magictrade.broker.registry import register_broker
from magictrade.broker.robinhood import RobinhoodBroker, RHOption, RHOptionOrder

API_KEY = "3KODWEPB1ZR37OT7"


@register_broker
class PaperMoneyBroker(Broker):
    name = 'papermoney'
    option = RHOption

    def __init__(self, balance: int = 1_000_000, data: Dict = {}, account_id: str = None,
                 date: str = None, data_files: List[Tuple[str, str]] = [],
                 options_data: Dict = [], exp_dates: Dict = {}, username: str = None,
                 password: str = None, mfa_code: str = None, token_file=None,
                 robinhood: bool = False, buying_power: float = 0.0):
        self._balance = balance
        self.stocks = {}
        self.options = {}
        self._date = date
        self.data = data
        self.options_data = options_data
        self.exp_dates = exp_dates
        self._buying_power = buying_power
        if not data:
            for df in data_files:
                data[df[0]] = {'history': {}}
                d = data[df[0]]['history']
                with open(os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'data', df[1])) as f:
                    for line in f:
                        date, price = line.split(',')
                        d[date] = float(price)
        if robinhood:
            self.rb = RobinhoodBroker(username, password, mfa_code, token_file)
            self._account_id = self.rb.account_id
        else:
            self._account_id = account_id

    @property
    def buying_power(self) -> float:
        return self._buying_power or self.rb.buying_power

    def options_positions(self) -> List:
        if not self.options:
            try:
                return self.rb.options_positions()
            except AttributeError:
                pass
        return {option['option']: option for option in self.options}

    def options_positions_data(self, options: List) -> List:
        if self.options_data:
            for option in options:
                for od in self.options_data:
                    if option['option'] == od['instrument']:
                        option.data.update(od)
                        break
            return options
        return self.rb.options_positions_data(options)

    def get_options(self, symbol: str, actually_work: bool = False) -> List:
        if actually_work:
            return self.options_data[symbol]
        elif self.options_data:
            return self.options_data
        return self.rb.get_options(symbol)

    def get_options_data(self, options: List) -> List:
        if self.options_data:
            return self.options_data
        return self.rb.get_options_data(options)

    def filter_options(self, options: List, exp_dates: List = [], option_type: str = None):
        if exp_dates:
            return [option for option in options if option["expiration_date"] == exp_dates[0]]
        elif option_type:
            return [RHOption(o) for o in options if o["type"] == option_type]

    def get_value(self) -> float:
        value = self.balance
        for equity in self.stocks:
            value += self.stocks[equity].value
        return value

    @property
    def date(self) -> datetime:
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
                # This is terrible but solves some growing pains :/
                try:
                    return self.data[symbol]['history'][date]
                except KeyError:
                    pass
            try:
                return self.data[symbol]['price']
            except KeyError:
                return 0
        else:
            data = requests.get('https://www.alphavantage.co/query', params={'function': 'GLOBAL_QUOTE',
                                                                             'symbol': symbol,
                                                                             'apikey': API_KEY
                                                                             }
                                )
            return float(data.json()['Global Quote']['02. open'])

    @property
    def balance(self) -> float:
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
                'option': leg.get('url') or leg.get('instrument'),
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
