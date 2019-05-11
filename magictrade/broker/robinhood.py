from datetime import datetime
from typing import Tuple, Any, List, Dict

from fast_arrow import Client, Stock, StockMarketdata, OptionChain, Option, OptionOrder, User, OptionPosition
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

    @property
    def date(self) -> str:
        return datetime.now()

    def get_quote(self, symbol: str) -> float:
        return float(StockMarketdata.quote_by_symbol(self.client, symbol)['last_trade_price'])

    @property
    def account_id(self) -> str:
        return self._account_id

    def get_value(self) -> float:
        raise NotImplementedError()

    @property
    def balance(self) -> float:
        return float(Account.all(self.client)[0]["cash"])

    def options_positions(self) -> List:
        return OptionPosition.all(self.client, nonzero=True)

    def options_positions_data(self, options: List) -> List:
        return OptionPosition.mergein_marketdata_list(self.client, options)

    @property
    def buying_power(self) -> float:
        return float(Account.all(self.client)[0]["buying_power"])

    def get_options(self, symbol: str) -> List:
        stock = Stock.fetch(self.client, symbol)

        return OptionChain.fetch(self.client, stock["id"], symbol)

    def filter_options(self, options: List, exp_dates: List):
        return Option.in_chain(self.client, options["id"], expiration_dates=exp_dates)

    def get_options_data(self, options: List) -> List:
        options = Option.mergein_marketdata_list(self.client, options)
        for option in options:
            for key, value in option:
                try:
                    option[key] = float(value)
                except ValueError:
                    pass
        return options

    def options_transact(self, legs: List[Dict], symbol: str, direction: str, price: float,
                         quantity: int, effect: str = 'open') -> Tuple[Any, Any]:
        if effect not in ('open', 'close') \
                or direction not in ('credit', 'debit'):
            raise InvalidOptionError()

        new_legs = []
        for leg, action, effect in legs:
            new_legs.append({
                'side': action,
                'option': leg['url'],
                'position_effect': effect,
                'ratio_quantity': '1'
            })

        oo = OptionOrder.submit(self.client, direction, legs,
                                str(abs(price)), quantity, "gfd", "immediate", "limit")
        return oo

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()
