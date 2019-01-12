import os
from typing import Tuple, Dict, List

from fast_arrow import Client, StockMarketdata, Stock, OptionChain, Option

from magictrade import Position
from magictrade.broker import Broker, InsufficientFundsError, NonexistentAssetError, InvalidOptionError


class PaperMoneyBroker(Broker):
    def __init__(self, balance: int = 1_000_000, data: Dict = {},
                 account_id: str = None, date: str = None, data_files: List[Tuple[str, str]] = []):
        self._balance = balance
        self.equities = {}
        self.options = {}
        self.date = date
        self.data = data
        if not data:
            for df in data_files:
                data[df[0]] = {}
                d = data[df[0]]
                with open(os.path.join(os.path.dirname(__file__), 'data', df[1])) as f:
                    for line in f:
                        date, price = line.split(',')
                        d[date] = float(price)
        self.client = Client()
        self._account_id = account_id

    def get_value(self) -> float:
        pass

    @property
    def account_id(self) -> str:
        return self._account_id

    def get_quote(self, symbol: str) -> float:
        if self.data:
            if self.date:
                return self.data[symbol]['history'][self.date]
            return self.data[symbol]['price']
        else:
            return float(StockMarketdata.quote_by_symbol(self.client, symbol)['last_trade_price'])

    @property
    def cash_balance(self) -> float:
        return self._balance

    @staticmethod
    def _format_option(symbol: str, expiration: str,
                       strike: float, option_type: str):
        return '{}:{}:{}{}'.format(symbol, expiration, strike,
                                   'c' if option_type == 'call' else 'p')

    def options_transact(self, symbol: str, expiration: str, strike: float,
                         quantity: int, option_type: str, action: str = 'buy',
                         effect: str = 'open') -> Tuple[str, Position]:
        if option_type not in ('call', 'put') or action not in ('buy', 'sell') \
                or effect not in ('open', 'close'):
            raise InvalidOptionError()

        if self.data:
            price = self.data[symbol]["options"][expiration][option_type][strike]
        else:
            stock = Stock.fetch(self.client, symbol)

            oc = OptionChain.fetch(self.client, stock["id"], symbol)
            if expiration not in oc['expiration_dates']:
                raise InvalidOptionError()
            ops = Option.in_chain(self.client, oc["id"], expiration_dates=[expiration])
            ops = list(filter(lambda x: x["type"] == option_type, ops))

            for op in ops:
                if op["strike_price"] == "{:.4f}".format(strike):
                    option_to_trade = op
                    break

            option_to_trade = Option.mergein_marketdata_list(self.client, [option_to_trade])[0]

            if action == 'buy' and effect == 'open':
                price = option_to_trade["bid_price"]
            elif action == 'sell' and effect == 'close':
                price = option_to_trade["ask_price"]
            else:
                raise NotImplementedError()

        if action == 'buy' and self.cash_balance - price < 0:
            raise InsufficientFundsError()
        option = self._format_option(symbol, expiration, strike, option_type)
        p = self.options.get(option)
        price = price * quantity * 100
        if not p:
            p = Position(symbol, price, quantity, self, option_type, strike, expiration)
            self.options[option] = p
        else:
            if effect == 'open':
                p.quantity += quantity
                p.cost += price
            else:
                p.quantity -= quantity
                p.cost -= price
        self._balance -= price * (-1 if effect == 'close' else 1)
        return 'success', p

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        debit = self.get_quote(symbol) * quantity
        if self.cash_balance - debit < 0:
            raise InsufficientFundsError()
        self._balance -= debit
        if self.equities.get(symbol):
            self.equities[symbol].quantity += quantity
            self.equities[symbol].cost += quantity
        else:
            self.equities[symbol] = Position(symbol, debit, quantity, self)
        return 'success', self.equities[symbol]

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        position = self.equities.get(symbol)
        if not position or position.quantity < quantity:
            raise NonexistentAssetError()
        credit = self.get_quote(symbol) * quantity
        self._balance += credit
        position.quantity -= quantity
        position.cost -= credit
        if position.cost < 0:
            position.cost == 0
        return 'success', position
