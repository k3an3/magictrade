import json
import os
from datetime import datetime
from typing import Tuple, Any, List, Dict

from fast_arrow import Client, Stock, OptionChain, Option, OptionOrder, OptionPosition, StockMarketdata, Portfolio
from fast_arrow.resources.account import Account

from magictrade import Broker
from magictrade.broker import InvalidOptionError

token_filename = '.oauth2-token'


class RobinhoodBroker(Broker):
    def __init__(self, username: str = None, password: str = None, mfa_code: str = None,
                 token_file: str = None):
        token_file = token_file or token_filename
        if not username and os.path.exists(token_file):
            with open(token_file) as f:
                j = json.load(f)
                kwargs = {'access_token': j.get('access_token'),
                          'refresh_token': j.get('refresh_token')}
        else:
            kwargs = {'username': username, 'password': password,
                      'mfa_code': mfa_code}
        # Necessary to build kwargs this way because Client init is funky
        self.client = Client(**kwargs)
        self.client.authenticate()
        self._account_id = Account.all(self.client)[0]['account_number']
        with open(token_file, "w") as f:
            json.dump({'access_token': self.client.access_token,
                       'refresh_token': self.client.refresh_token}, f)
        self.portfolio = None

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
    def balance(self, update: bool = True) -> float:
        return float(Portfolio.fetch(self.client, self.account_id)["equity"])

    @property
    def buying_power(self) -> float:
        return float(Account.all(self.client)[0]["buying_power"])

    def options_positions(self) -> List:
        return OptionPosition.all(self.client, nonzero=True)

    @staticmethod
    def _normalize_options_data(options):
        for option in options:
            for key, value in option.items():
                try:
                    option[key] = float(value)
                except (ValueError, TypeError):
                    pass
        return options

    def options_positions_data(self, options: List) -> List:
        return self._normalize_options_data(OptionPosition.mergein_marketdata_list(self.client, options))

    def get_options(self, symbol: str) -> List:
        stock = Stock.fetch(self.client, symbol)

        return OptionChain.fetch(self.client, stock["id"], symbol)

    def filter_options_by_date(self, options: List, exp_dates: List):
        return Option.in_chain(self.client, options["id"], expiration_dates=exp_dates)

    def get_options_data(self, options: List) -> List:
        return self._normalize_options_data(Option.mergein_marketdata_list(self.client, options))

    def options_transact(self, legs: List[Dict], direction: str, price: float,
                         quantity: int, effect: str = 'open', time_in_force: str = 'gfd') -> Tuple[Any, Any]:
        if effect not in ('open', 'close') \
                or direction not in ('credit', 'debit'):
            raise InvalidOptionError()

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
                'ratio_quantity': str(int(leg.get('ratio_quantity', 1)))
            })

        oo = OptionOrder.submit(self.client, direction, new_legs,
                                str(abs(round(price, 2))), quantity, time_in_force, "immediate", "limit")
        return oo

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError()

    def cancel_order(self, ref_id: str):
        return OptionOrder.cancel(self.client, ref_id)

    def replace_order(self, order: Dict):
        return OptionOrder.replace(self.client, order, order['price'])

    def get_order(self, ref_id: str):
        return OptionOrder.get(self.client, ref_id)
