import datetime
from typing import Tuple, Any, List, Dict

from tdameritrade import TDClient
from tdameritrade.auth import refresh_token

from magictrade.broker import Broker, InvalidOptionError
from magictrade.broker.registry import register_broker


@register_broker
class TDAmeritradeBroker(Broker):
    name = 'td_ameritrade'

    def __init__(self, client_id: str = None, account_id: str = None, access_token: str = None,
                 refresh_token: str = None):
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
        return [p for p in self._get_account(positions=True)['positions'] if p['instrument']['assetType'] == 'OPTION']

    @staticmethod
    def _strip_exp(options: Any) -> Any:
        if isinstance(options, dict):
            return {key.split(':')[0]: value for key, value in options.items()}
        else:
            return [d.split(':')[0] for d in options]

    def get_options(self, symbol: str) -> Dict:
        options = self.client.options(symbol)
        return {
            'expiration_dates': self._strip_exp(options['callExpDateMap'].keys()),
            'puts': self._strip_exp(options['putExpDateMap']),
            'calls': self._strip_exp(options['callExpDateMap'])
        }

    def filter_options(self, options: Dict, exp_dates: List = [], option_type: str = None) -> List:
        if exp_dates:
            puts = {}
            calls = {}
            for exp_date in exp_dates:
                puts.update(options['puts'][exp_date])
                calls.update(options['calls'][exp_date])
            return {
                'put': puts,
                'call': calls,
            }
        elif option_type:
            return [option[0] for option in options[option_type.lower()].values()]

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
        raise NotImplementedError

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Any]:
        raise NotImplementedError
