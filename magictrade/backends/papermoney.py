from typing import Tuple, Dict

from fast_arrow import Client, StockMarketdata, Stock, OptionChain, Option

from magictrade import Position
from magictrade.backends import Backend, InsufficientFundsError, NonexistentAssetError, InvalidOptionError


class PaperMoneyBackend(Backend):
    def __init__(self, balance: int = 1_000_000, data: Dict = {}, api_key: str = None):
        self._balance = balance
        self.equities = {}
        self.options = {}
        self.data = data
        self.api_key = api_key
        self.client = Client()

    def get_quote(self, symbol: str, date: str = None) -> float:
        if self.data:
            if date:
                for key in self.data.get(symbol):
                    if "Time Series" in key:
                        return float(self.data.get(symbol)[key][date]['1. open'])
            else:
                return float(self.data.get(symbol)['Global Quote']['05. price'])
        else:
            return float(StockMarketdata.quote_by_symbol(self.client, symbol)['last_trade_price'])

    @property
    def balance(self) -> float:
        return self._balance

    def options_transact(self, symbol: str, expiration: str, strike: float,
                         quantity: int, option_type: str, action: str = 'buy',
                         effect: str = 'open') -> Tuple[str, Position]:
        if option_type not in ('call', 'put') or action not in ('buy', 'sell') \
                or effect not in ('open', 'close'):
            raise InvalidOptionError()

        if self.data:
            price = self.data[symbol]["Options"][expiration][option_type][strike]
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

        if action == 'buy' and self.balance - price < 0:
            raise InsufficientFundsError()
        p = self.options.get('{}:{}:{}'.format(symbol, expiration, strike))
        if not p:
            p = Position(symbol, price * 100, quantity, self, option_type, strike, expiration)
            self.options['{}:{}:{}'.format(symbol, expiration, strike)] = p
        else:
            if effect == 'open':
                p.quantity += quantity
                p.cost += price * 100
            else:
                p.quantity -= quantity
                p.cost -= price * 100
        self._balance -= price * 100 * (-1 if effect == 'close' else 1)
        return 'success', p

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        debit = self.get_quote(symbol) * quantity
        if self.balance - debit < 0:
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
        self._balance -= credit
        position.quantity -= quantity
        position.cost -= credit
        return 'success', position
