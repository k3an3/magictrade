from typing import Tuple, Any

from fast_arrow import Client, Stock, StockMarketdata, OptionChain, Option, OptionOrder
from paperbroker.accounts import Account

from magictrade import Backend, Position
from magictrade.backends import InvalidOptionError


class RobinhoodBackend(Backend):
    def __init__(self, username: str, password: str, mfa_token: str = None):
        self.client = Client(username, password, mfa_token)
        self.client.authenticate()

    def get_quote(self, symbol: str, date: str) -> float:
        return float(StockMarketdata.quote_by_symbol(self.client, symbol)['last_trade_price'])

    @property
    def balance(self) -> float:
        return float(Account.all(self.client)["results"][0]["margin_balances"]["cash"])

    def options_transact(self, symbol: str, expiration: str, strike: float, quantity: int, option_type: str,
                         direction: str) -> Tuple[Any, Any]:
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

        oo = OptionOrder.submit(self.client, direction, legs,
                                price, quantity, "gfd", "immediate", "limit")
        return oo, Position(symbol, price * 100, quantity, self, option_type, strike, expiration)

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()
