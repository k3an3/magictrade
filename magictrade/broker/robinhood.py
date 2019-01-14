from typing import Tuple, Any

from fast_arrow import Client, Stock, StockMarketdata, OptionChain, Option, OptionOrder, User
from fast_arrow.resources.account import Account

from magictrade import Broker, Position
from magictrade.broker import InvalidOptionError


class RobinhoodBroker(Broker):
    def __init__(self, username: str, password: str, mfa_code: str = None):
        self.client = Client(username=username,
                             password=password,
                             mfa_code=mfa_code)
        self.client.authenticate()
        self._account_id = Account.all(self.client)[0]['account_number']

    def get_quote(self, symbol: str) -> float:
        return float(StockMarketdata.quote_by_symbol(self.client, symbol)['last_trade_price'])

    @property
    def account_id(self) -> str:
        return self._account_id

    def get_value(self) -> float:
        raise NotImplementedError()

    @property
    def cash_balance(self) -> float:
        return float(Account.all(self.client)[0]["margin_balances"]["cash"])

    def options_transact(self, symbol: str, expiration: str, strike: float,
                         quantity: int, option_type: str, action: str = 'buy',
                         effect: str = 'open') -> Tuple[Any, Any]:
        if option_type not in ('call', 'put') or action not in ('buy', 'sell') \
                or effect not in ('open', 'close'):
            raise InvalidOptionError()

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
            direction = 'debit'
            price = option_to_trade["bid_price"]
        elif action == 'sell' and effect == 'close':
            direction = 'credit'
            price = option_to_trade["ask_price"]
        else:
            raise NotImplementedError()

        legs = [{
            "side": action,
            "option": option_to_trade["url"],
            "position_effect": effect,
            "ratio_quantity": 1
        }]

        oo = OptionOrder.submit(self.client, direction, legs,
                                price, quantity, "gfd", "immediate", "limit")
        return oo, Position(symbol, price * 100, quantity, self, option_type, strike, expiration)

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()