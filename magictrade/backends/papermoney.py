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
                         quantity: int, option_type: str, direction: str) -> Tuple[str, Position]:

        if option_type not in ('call', 'put') or direction not in ('credit', 'debit'):
            raise InvalidOptionError()

        stock = Stock.fetch(self.client, symbol)

        oc = OptionChain.fetch(self.client, stock["id"], symbol)
        if expiration not in oc['expiration_dates']:
            raise InvalidOptionError()
        ops = Option.in_chain(self.client, oc["id"], expiration_dates=[expiration])
        ops = list(filter(lambda x: x["type"] == option_type, ops))

        for op in ops:
            if op["strike_price"] == "{:.4f}".format(strike):
                option_to_buy = op
                break

        option_to_buy = Option.mergein_marketdata_list(self.client, [option_to_buy])[0]
        legs = [{
            "side": "buy",
            "option": option_to_buy["url"],
            "position_effect": "open",
            "ratio_quantity": 1
        }]

        price = option_to_buy["bid_price"]

        tPosition(symbol, price * 100, quantity, self, option_type, strike, expiration)

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
