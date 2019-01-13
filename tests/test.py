import pytest

from magictrade import storage
from magictrade.broker import InsufficientFundsError, NonexistentAssetError
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy
from magictrade.utils import get_account_history

"3KODWEPB1ZR37OT7"

quotes = {
    'SPY': {
        "price": 252.3900,
        "history": {
            '2019-01-01': 255.55,
            '2019-01-02': 254.87,
            '2019-01-03': 253.26,
            '2019-01-04': 256.01,
            '2019-01-05': 253.11,
        },
        "volume": 142628834,
        "options": {
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
        "price": 101.9300,
    },
}

human_quotes_1 = {
    'TST': {
        'history': {
            1: 250,
            2: 251,
            3: 252,
            4: 253,
            5: 254,
        }
    }
}


class TestPaperMoney:
    def test_default_balance(self):
        pmb = PaperMoneyBroker()
        assert pmb.cash_balance == 1_000_000

    def test_balance(self):
        pmb = PaperMoneyBroker(balance=12_345)
        assert pmb.cash_balance == 12_345

    def test_quote(self):
        pmb = PaperMoneyBroker(data=quotes)
        assert pmb.get_quote('SPY') == 252.39

    def test_purchase_equity(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.stocks['SPY'].quantity == 100
        assert pmb.stocks['SPY'].cost == 25_239
        assert pmb.cash_balance == 974_761

    def test_sell_equity(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 100)
        assert not pmb.stocks.get('SPY')
        assert pmb.cash_balance == 1_000_000

    def test_sell_equity_2(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 50)
        assert pmb.stocks['SPY'].quantity == 50
        assert round(pmb.stocks['SPY'].cost, 2) == 25_239 / 2

    def test_buy_sell_multiple(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('MSFT', 12)
        pmb.buy('SPY', 97)
        pmb.sell('MSFT', 5)
        pmb.sell('SPY', 50)
        assert pmb.stocks['MSFT'].quantity == 7
        assert pmb.stocks['MSFT'].cost == 713.51
        assert pmb.stocks['SPY'].quantity == 47
        assert round(pmb.stocks['SPY'].cost, 2) == 11_862.33

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
        assert pmb.cash_balance == 989_630.0
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 10
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 10_370

    def test_buy_option_1(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        assert pmb.cash_balance == 979_260.0
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 20
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 20_740

    def test_buy_option_2(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-11', 249.5, 5, 'put')
        assert pmb.cash_balance == 984545
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 10
        assert pmb.options['SPY:2019-07-11:249.5p'].quantity == 5
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 10_370
        assert round(pmb.options['SPY:2019-07-11:249.5p'].cost) == 5_085

    def test_sell_option(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call',
                             action='sell', effect='close')
        assert pmb.cash_balance == 1_000_000
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 0
        assert pmb.options['SPY:2019-07-04:250.0c'].cost == 0

    def test_sell_option_1(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 5, 'call',
                             action='sell', effect='close')
        assert pmb.cash_balance == 994_815
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 5
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 5_185

    def test_holding_value(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.stocks['SPY'].value == 25_239

    def test_account_value(self):
        pmb = PaperMoneyBroker(data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.get_value() == 1_000_000

    def test_historic_quote(self):
        pmb = PaperMoneyBroker(date='2019-01-03', data=quotes)
        assert pmb.get_quote('SPY') == 253.26

    def test_historic_quote_1(self):
        pmb = PaperMoneyBroker(date='2019-01-03', data=quotes)
        pmb.date = '2019-01-04'
        assert pmb.get_quote('SPY') == 256.01

    def test_time_buy_sell(self):
        pmb = PaperMoneyBroker(date='2019-01-01', data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.stocks['SPY'].value == 25_555
        pmb.date = '2019-01-04'
        assert pmb.stocks['SPY'].value == 25_601
        pmb.sell('SPY', 100)
        assert pmb.cash_balance == 1_000_046


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


class TestBAHStrategy:
    def test_buy_and_hold(self):
        pmb = PaperMoneyBroker(data=quotes)
        ts = BuyandHoldStrategy(pmb)
        assert ts.make_trade('SPY')
        assert pmb.stocks['SPY'].quantity == 3962

    def test_buy_and_hold_1(self):
        pmb = PaperMoneyBroker(data=quotes)
        ts = BuyandHoldStrategy(pmb)
        ts.make_trade('SPY')
        assert not ts.make_trade('SPY')

    def test_buy_and_hold_fail(self):
        pmb = PaperMoneyBroker(balance=100, data=quotes)
        ts = BuyandHoldStrategy(pmb)
        assert not ts.make_trade('SPY')
        assert not pmb.stocks.get('SPY')


class TestHumanStrategy:
    def test_get_percentage_change(self):
        assert HumanTradingStrategy.get_percentage_change(100, 200) == 100

    def test_get_percentage_change_1(self):
        assert round(HumanTradingStrategy.get_percentage_change(100, 100.57), 2) == 0.57

    def test_get_percentage_change_2(self):
        assert HumanTradingStrategy.get_percentage_change(100, 50) == -50
