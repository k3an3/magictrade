import pytest

from magictrade import storage
from magictrade.broker import InsufficientFundsError, NonexistentAssetError
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy, DEFAULT_CONFIG
from magictrade.strategy.reactive import ReactiveStrategy
from magictrade.utils import get_account_history, get_percentage_change
from tests.data import quotes, human_quotes_1, reactive_quotes

"3KODWEPB1ZR37OT7"


class TestPaperMoney:
    def test_date(self):
        pmb = PaperMoneyBroker(date='1234')
        assert pmb.date == '1234'
        pmb.date = '5555'
        assert pmb.date == '5555'

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


class TestUtils:
    def test_get_percentage_change(self):
        assert get_percentage_change(100, 200) == 100
        assert round(get_percentage_change(100, 100.57), 2) == 0.57
        assert get_percentage_change(100, 50) == -50


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


class TestReactiveStrategy:
    def test_reactive(self):
        pmb = PaperMoneyBroker(balance=100, data=reactive_quotes, date=1)
        rts = ReactiveStrategy(pmb)
        assert rts.make_trade('TST') == ('buy', 10)
        pmb.date += 1
        assert rts.make_trade('TST') == ('buy', 0)
        pmb.date += 1
        assert rts.make_trade('TST') == ('buy', 0)
        pmb.date += 1
        assert rts.make_trade('TST') == ('buy', 0)
        pmb.date += 1
        assert rts.make_trade('TST') == ('sell', 10)
        pmb.date += 1
        assert rts.make_trade('TST') == ('buy', 10)
        pmb.date += 1
        assert rts.make_trade('TST') == ('sell', 10)
        pmb.date += 1
        assert rts.make_trade('TST') == ('sell', 0)
        pmb.date += 1
        assert rts.make_trade('TST') == ('buy', 10)


class TestHumanStrategy:
    def test_config_init(self):
        hts = HumanTradingStrategy(None, {'peak_window': 45})
        assert hts.config['peak_window'] == 45
        assert hts.config['stop_loss_pct'] == DEFAULT_CONFIG['stop_loss_pct']

    def test_get_quantity(self):
        pmb = PaperMoneyBroker()
        hts = HumanTradingStrategy(pmb, config={'max_equity': 5_000})
        assert hts._get_quantity(252.39) == 19
        assert hts._get_quantity(5_001) == 0

    def test_get_window_chg(self):
        storage.delete('TST')
        pmb = PaperMoneyBroker()
        hts = HumanTradingStrategy(pmb, config={'short_window': 10})
        assert hts._get_window_change('TST', 'short') == 0.0
        storage.delete('TST')

    def test_get_window_chg_1(self):
        storage.delete('TST')
        storage.rpush('TST', *range(1, 6))
        pmb = PaperMoneyBroker()
        hts = HumanTradingStrategy(pmb, config={'short_window': 10})
        assert hts._get_window_change('TST', 'short') == 400.0
        storage.delete('TST')

    def test_get_window_chg_2(self):
        storage.delete('TST')
        storage.rpush('TST', *range(1, 31))
        pmb = PaperMoneyBroker()
        hts = HumanTradingStrategy(pmb, config={'short_window': 11})
        assert hts._get_window_change('TST', 'short') == 50.0
        storage.delete('TST')

    def test_get_window_chg_3(self):
        storage.delete('TST')
        storage.rpush('TST', *range(31, 1, -1))
        pmb = PaperMoneyBroker()
        hts = HumanTradingStrategy(pmb, config={'short_window': 9})
        assert hts._get_window_change('TST', 'short') == -80.0
        storage.delete('TST')

    def test_algo(self):
        storage.delete('TST')
        storage.delete('sell')
        storage.delete('buy')
        config = {
            'peak_window': 30,
            'sample_frequency_minutes': 5,
            'stop_loss_pct': 10,
            'take_gain_pct': 20,
            'max_equity': 1_000,
            'short_window': 6,
            'short_window_pct': 15,
            'med_window': 10,
            'med_window_pct': 100,
            'long_window': 20,
            'long_window_pct': 200,
        }
        pmb = PaperMoneyBroker(date=1, data=human_quotes_1)
        hts = HumanTradingStrategy(pmb, config=config)
        for i in range(70):
            hts.make_trade('TST')
            pmb.date += 1
        assert hts.trades.get(3) == ('buy', 'TST', 83, 'short window met')
        assert hts.trades.get(56) == ('sell', 'TST', 83, 'take gain off peak')
        assert int(storage.get('buy')) == 1
        assert int(storage.get('sell')) == 1
