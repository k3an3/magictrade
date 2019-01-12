import json
import os

import pytest

from magictrade import storage
from magictrade.broker import InsufficientFundsError, NonexistentAssetError
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.utils import get_account_history

"3KODWEPB1ZR37OT7"

quotes = {
    'SPY': {
        "Global Quote": {
            "01. symbol": "SPY",
            "02. open": "247.5900",
            "03. high": "253.1100",
            "04. low": "247.1700",
            "05. price": "252.3900",
            "06. volume": "142628834",
            "07. latest trading day": "2019-01-04",
            "08. previous close": "244.2100",
            "09. change": "8.1800",
            "10. change percent": "3.3496%"
        },
        "Options": {
            '2019-07-04': {
                'call': {
                    249.5: 10.58,
                    250.0: 10.37,
                    250.5: 10.14,
                    251.0: 10.01,
                },
                'put': {
                    249.5: 8.47,
                    250.0: 9.00,
                    250.5: 9.25,
                    251.0: 10.02,
                }
            },
            '2019-07-11': {
                'call': {
                    249.5: 11.42,
                    250.0: 11.07,
                    250.5: 10.84,
                    251.0: 10.51,
                },
                'put': {
                    249.5: 10.17,
                    250.0: 10.68,
                    250.5: 10.98,
                    251.0: 11.92,
                }
            }
        }
    },
    'MSFT': {
        "Global Quote": {
            "01. symbol": "MSFT",
            "02. open": "99.7200",
            "03. high": "102.5100",
            "04. low": "98.9300",
            "05. price": "101.9300",
            "06. volume": "44060620",
            "07. latest trading day": "2019-01-04",
            "08. previous close": "97.4000",
            "09. change": "4.5300",
            "10. change percent": "4.6509%"
        },
    },
}

with open(os.path.join(os.path.dirname(__file__), 'data', 'SPY_5min_intraday.json')) as f:
    dataset1 = json.loads(f.read())


class TestPaperMoney:
    def test_default_balance(self):
        pmb = PaperMoneyBroker()
        assert pmb.balance == 1_000_000

    def test_balance(self):
        pmb = PaperMoneyBroker(balance=12_345)
        assert pmb.balance == 12_345

    def test_quote(self):
        pmb = PaperMoneyBroker(data=quotes)
        assert pmb.get_quote('SPY') == 252.39

    def test_intraday_price(self):
        pmb = PaperMoneyBroker(data={'SPY': dataset1})
        assert pmb.get_quote('SPY', '2019-01-04 12:20:00') == 251.375

    def test_purchase_equity(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.equities['SPY'].quantity == 100
        assert pmb.equities['SPY'].cost == 25_239

    def test_sell_equity(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 100)
        assert pmb.equities['SPY'].quantity == 0
        assert pmb.equities['SPY'].cost == 0

    def test_sell_equity_2(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 50)
        assert pmb.equities['SPY'].quantity == 50
        assert round(pmb.equities['SPY'].cost, 2) == 25_239 / 2

    def test_buy_sell_multiple(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('MSFT', 12)
        pmb.buy('SPY', 97)
        pmb.sell('MSFT', 5)
        pmb.sell('SPY', 50)
        assert pmb.equities['MSFT'].quantity == 7
        assert pmb.equities['MSFT'].cost == 713.51
        assert pmb.equities['SPY'].quantity == 47
        assert round(pmb.equities['SPY'].cost, 2) == 11_862.33

    def test_exceeds_balance(self):
        pmb = PaperMoneyBroker(balance=100, data=quotes)
        with pytest.raises(InsufficientFundsError):
            pmb.buy('SPY', 1)

    def test_exceeds_holdings(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 1)
        with pytest.raises(NonexistentAssetError):
            pmb.sell('SPY', 2)

    def test_sell_no_holdings(self):
        pmb = PaperMoneyBroker(data=quotes)
        with pytest.raises(NonexistentAssetError):
            pmb.sell('SPY', 1)

    def test_buy_option(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        assert pmb.balance == 989_630.0
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 10
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 10_370

    def test_buy_option_1(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        assert pmb.balance == 979_260.0
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 20
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 20_740

    def test_buy_option_2(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-11', 249.5, 5, 'put')
        assert pmb.balance == 984545
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 10
        assert pmb.options['SPY:2019-07-11:249.5p'].quantity == 5
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 10_370
        assert round(pmb.options['SPY:2019-07-11:249.5p'].cost) == 5_085

    def test_sell_option(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call',
                             action='sell', effect='close')
        assert pmb.balance == 1_000_000
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 0
        assert pmb.options['SPY:2019-07-04:250.0c'].cost == 0

    def test_sell_option_1(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 5, 'call',
                             action='sell', effect='close')
        assert pmb.balance == 994_815
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 5
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 5_185


class TestLogging:
    def test_account_history(self):
        storage.delete('test:dates')
        storage.delete('test:values')
        pmb = PaperMoneyBroker(account_id='test')
        pmb.log_balance()
        _, h = get_account_history(pmb.account_id)
        assert len(h) == 1
        assert h[0] == 1_000_000
        storage.delete('test:dates')
        storage.delete('test:values')

    def test_account_history_1(self):
        storage.delete('test:dates')
        storage.delete('test:values')
        pmb = PaperMoneyBroker(account_id='test')
        pmb.log_balance()
        pmb._balance = 5_000_000
        pmb.log_balance()
        pmb._balance = 1_234
        pmb.log_balance()
        _, h = get_account_history(pmb.account_id)
        assert len(h) == 3
        assert h[0] == 1_000_000
        assert h[1] == 5_000_000
        assert h[2] == 1_234
        storage.delete('test:dates')
        storage.delete('test:values')
