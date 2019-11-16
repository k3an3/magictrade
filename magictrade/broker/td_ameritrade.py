import datetime
from typing import Tuple, Any, List, Dict

from tdameritrade import TDClient
from tdameritrade.auth import refresh_token

from magictrade import Broker
from magictrade.broker import InvalidOptionError


class TDAmeritradeBroker(Broker):
    def __init__(self, client_id: str, account_id: str = None, access_token: str = None, refresh_token: str = None):
        self.client = TDClient(access_token=access_token, accountIds=[account_id], refresh_token=refresh_token,
                               client_id=client_id)
        if not access_token:
            self.refresh()
        self.client.accounts()
        self._account_id = account_id

    def refresh(self):
        self.client._token = refresh_token(self.client.refresh_token, self.client.client_id)['access_token']

    def get_quote(self, symbol: str) -> float:
        return self.client.quote(symbol)[symbol]['lastPrice']

    def _get_account(self, **kwargs):
        return self.client.accounts(**kwargs)[self._account_id]['securitiesAccount']

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def balance(self) -> float:
        return self._get_account()['currentBalances']['liquidationValue']

    @property
    def buying_power(self) -> float:
        return self._get_account()['initialBalances']['totalCash']

    def get_value(self) -> float:
        raise NotImplementedError()

    def options_positions(self) -> List:
        return [p for p in self._get_account(positions=True)['positions'] if p['instrument']['asset_type'] == 'OPTION']

    def get_options(self, symbol: str) -> List:
        options = self.client.options(symbol)

    def filter_options(self, options: List, exp_dates: List) -> List:
        for strike, data in options:
            data = data[0]
            exp_date = datetime.fromtimestamp(data['expirationDate']).strftime('%Y-%m-%d')
            if exp_date in exp_dates:
                yield data

    def options_transact(self, legs: List[Dict], direction: str, price: float,
                         quantity: int, effect: str = 'open', time_in_force: str = 'gfd') -> Tuple[Any, Any]:
        if effect not in ('open', 'close'):
            raise InvalidOptionError()

        effect = {'open': 'TO_OPEN',
                  'close': 'TO_CLOSE'
                  }[effect]

        new_legs = []
        for leg in legs:
            if len(leg) == 2:
                leg, action = leg
            else:
                action = leg['side']
            new_legs.append({
                'instruction': '_'.join((action.upper(), effect)),
                'quantity': leg.get('quantity', 1),
                'instrument': leg['instrument'],
            })

        return self.client.trade_options(self._account_id, new_legs, price, order_type='LIMIT', strategy='CUSTOM')

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        pass

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        pass
