import uuid
from datetime import timedelta, datetime

import pytest

from magictrade import storage
from magictrade.broker import InsufficientFundsError, NonexistentAssetError, InvalidOptionError
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy, DEFAULT_CONFIG
from magictrade.strategy.optionalpha import OptionAlphaTradingStrategy, strategies, TradeException, high_iv
from magictrade.strategy.reactive import ReactiveStrategy
from magictrade.utils import get_account_history, get_percentage_change
from tests.data import quotes, human_quotes_1, reactive_quotes, oa_options_1, exp_dates

"3KODWEPB1ZR37OT7"

date = datetime.strptime("2019-03-31", "%Y-%m-%d")


class TestPaperMoney:
    def test_date(self):
        pmb = PaperMoneyBroker(account_id='test', date='1234')
        assert pmb.date == '1234'
        pmb.date = '5555'
        assert pmb.date == '5555'

    def test_default_balance(self):
        pmb = PaperMoneyBroker(account_id='test')
        assert pmb.balance == 1_000_000

    def test_balance(self):
        pmb = PaperMoneyBroker(account_id='test', balance=12_345)
        assert pmb.balance == 12_345

    def test_quote(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        assert pmb.get_quote('SPY') == 252.39

    def test_purchase_equity(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.stocks['SPY'].quantity == 100
        assert pmb.stocks['SPY'].cost == 25_239
        assert pmb.balance == 974_761

    def test_sell_equity(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 100)
        assert not pmb.stocks.get('SPY')
        assert pmb.balance == 1_000_000

    def test_sell_equity_2(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 50)
        assert pmb.stocks['SPY'].quantity == 50
        assert round(pmb.stocks['SPY'].cost, 2) == 25_239 / 2

    def test_buy_sell_multiple(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('MSFT', 12)
        pmb.buy('SPY', 97)
        pmb.sell('MSFT', 5)
        pmb.sell('SPY', 50)
        assert pmb.stocks['MSFT'].quantity == 7
        assert pmb.stocks['MSFT'].cost == 713.51
        assert pmb.stocks['SPY'].quantity == 47
        assert round(pmb.stocks['SPY'].cost, 2) == 11_862.33

    def test_exceeds_balance(self):
        pmb = PaperMoneyBroker(account_id='test', balance=100, data=quotes)
        with pytest.raises(InsufficientFundsError):
            pmb.buy('SPY', 1)

    def test_exceeds_holdings(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('SPY', 1)
        with pytest.raises(NonexistentAssetError):
            pmb.sell('SPY', 2)

    def test_sell_no_holdings(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        with pytest.raises(NonexistentAssetError):
            pmb.sell('SPY', 1)

    """
    def test_buy_option(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        assert pmb.balance == 989_630.0
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 10
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 10_370

    def test_buy_option_1(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        assert pmb.balance == 979_260.0
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 20
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 20_740

    def test_buy_option_2(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-11', 249.5, 5, 'put')
        assert pmb.balance == 984545
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 10
        assert pmb.options['SPY:2019-07-11:249.5p'].quantity == 5
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 10_370
        assert round(pmb.options['SPY:2019-07-11:249.5p'].cost) == 5_085

    def test_sell_option(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call',
                             action='sell', effect='close')
        assert pmb.balance == 1_000_000
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 0
        assert pmb.options['SPY:2019-07-04:250.0c'].cost == 0

    def test_sell_option_1(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.options_transact('SPY', '2019-07-04', 250.0, 10, 'call')
        pmb.options_transact('SPY', '2019-07-04', 250.0, 5, 'call',
                             action='sell', effect='close')
        assert pmb.balance == 994_815
        assert pmb.options['SPY:2019-07-04:250.0c'].quantity == 5
        assert round(pmb.options['SPY:2019-07-04:250.0c'].cost) == 5_185
    """

    def test_holding_value(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.stocks['SPY'].value == 25_239

    def test_account_value(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.get_value() == 1_000_000

    def test_historic_quote(self):
        pmb = PaperMoneyBroker(account_id='test', date='2019-01-03', data=quotes)
        assert pmb.get_quote('SPY') == 253.26

    def test_historic_quote_1(self):
        pmb = PaperMoneyBroker(account_id='test', date='2019-01-03', data=quotes)
        pmb.date = '2019-01-04'
        assert pmb.get_quote('SPY') == 256.01

    def test_time_buy_sell(self):
        pmb = PaperMoneyBroker(account_id='test', date='2019-01-01', data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.stocks['SPY'].value == 25_555
        pmb.date = '2019-01-04'
        assert pmb.stocks['SPY'].value == 25_601
        pmb.sell('SPY', 100)
        assert pmb.balance == 1_000_046


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
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        ts = BuyandHoldStrategy(pmb)
        assert ts.make_trade('SPY')
        assert pmb.stocks['SPY'].quantity == 3962

    def test_buy_and_hold_1(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        ts = BuyandHoldStrategy(pmb)
        ts.make_trade('SPY')
        assert not ts.make_trade('SPY')

    def test_buy_and_hold_fail(self):
        pmb = PaperMoneyBroker(account_id='test', balance=100, data=quotes)
        ts = BuyandHoldStrategy(pmb)
        assert not ts.make_trade('SPY')
        assert not pmb.stocks.get('SPY')


class TestReactiveStrategy:
    def test_reactive(self):
        pmb = PaperMoneyBroker(account_id='test', balance=100, data=reactive_quotes, date=1)
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
        pmb = PaperMoneyBroker(account_id='test', )
        hts = HumanTradingStrategy(pmb, config={'max_equity': 5_000})
        assert hts._get_quantity(252.39) == 19
        assert hts._get_quantity(5_001) == 0

    def test_get_window_chg(self):
        storage.delete('TST')
        pmb = PaperMoneyBroker(account_id='test', )
        hts = HumanTradingStrategy(pmb, config={'short_window': 10})
        assert hts._get_window_change('TST', 'short') == 0.0
        storage.delete('TST')

    def test_get_window_chg_1(self):
        storage.delete('TST')
        storage.rpush('TST', *range(1, 6))
        pmb = PaperMoneyBroker(account_id='test', )
        hts = HumanTradingStrategy(pmb, config={'short_window': 10})
        assert hts._get_window_change('TST', 'short') == 400.0
        storage.delete('TST')

    def test_get_window_chg_2(self):
        storage.delete('TST')
        storage.rpush('TST', *range(1, 31))
        pmb = PaperMoneyBroker(account_id='test', )
        hts = HumanTradingStrategy(pmb, config={'short_window': 11})
        assert hts._get_window_change('TST', 'short') == 50.0
        storage.delete('TST')

    def test_get_window_chg_3(self):
        storage.delete('TST')
        storage.rpush('TST', *range(31, 1, -1))
        pmb = PaperMoneyBroker(account_id='test', )
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
        pmb = PaperMoneyBroker(account_id='test', date=1, data=human_quotes_1)
        hts = HumanTradingStrategy(pmb, config=config)
        for i in range(70):
            hts.make_trade('TST')
            pmb.date += 1
        assert hts.trades.get(3) == ('buy', 'TST', 83, 'short window met')
        assert hts.trades.get(56) == ('sell', 'TST', 83, 'take gain off peak')
        assert int(storage.get('buy')) == 1
        assert int(storage.get('sell')) == 1


class TestOAStrategy:
    def test_filter_option_type_call(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        for option in oab._filter_option_type(oa_options_1, 'call'):
            assert option['type'] == 'call'

    def test_filter_option_type_put(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        for option in oab._filter_option_type(oa_options_1, 'put'):
            assert option['type'] == 'put'

    def test_find_probability_call_short(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        calls = oab._filter_option_type(oa_options_1, 'call')
        assert oab._find_option_with_probability(calls, 70, 'short')['id'] == '9d870f5d-bd44-4750-8ff6-7aee58249b9f'

    def test_find_probability_call_long(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        calls = oab._filter_option_type(oa_options_1, 'call')
        assert oab._find_option_with_probability(calls, 48, 'long')['id'] == '03facad1-959d-4674-85d5-79d50ff75ea6'

    def test_find_probability_put_short(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = oab._filter_option_type(oa_options_1, 'put')
        assert oab._find_option_with_probability(puts, 72, 'short')['id'] == 'f3acdb4d-82da-417b-ad13-5255613745bd'

    def test_find_probability_put_long(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = oab._filter_option_type(oa_options_1, 'put')
        assert oab._find_option_with_probability(puts, 27, 'long')['id'] == 'f3acdb4d-82da-417b-ad13-5255613745bd'

    def test_get_long_leg_put(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = oab._filter_option_type(oa_options_1, 'put')
        for option in puts:
            if option['strike_price'] == 38.5:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'put', width=1)['strike_price'] == 37.5

    def test_get_long_leg_put_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = oab._filter_option_type(oa_options_1, 'put')
        for option in puts:
            if option['strike_price'] == 38.5:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'put', width=2.5)['strike_price'] == 36.0

    def test_get_long_leg_call(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = oab._filter_option_type(oa_options_1, 'call')
        for option in puts:
            if option['strike_price'] == 38.0:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'call', width=1)['strike_price'] == 39.0

    def test_get_long_leg_call_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = oab._filter_option_type(oa_options_1, 'call')
        for option in puts:
            if option['strike_price'] == 38.0:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'call', width=2.5)['strike_price'] == 40.5

    def test_iron_butterfly(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        wings = oab.iron_butterfly(strategies['iron_butterfly'], oa_options_1, quote=39.5)
        assert wings[0][0]['strike_price'] == 39.5
        assert wings[1][0]['strike_price'] == 39.5
        assert wings[2][0]['strike_price'] == 42.0
        assert wings[3][0]['strike_price'] == 36.5
        assert wings[0][1:] == ('sell', 'open')
        assert wings[1][1:] == ('sell', 'open')
        assert wings[2][1:] == ('buy', 'open')
        assert wings[3][1:] == ('buy', 'open')

    def test_iron_butterfly_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        strategies['iron_butterfly']['probability'] = 75
        wings = oab.iron_butterfly(strategies['iron_butterfly'], oa_options_1, quote=39.5)
        assert wings[0][0]['strike_price'] == 39.5
        assert wings[1][0]['strike_price'] == 39.5
        assert wings[2][0]['strike_price'] == 40.5
        assert wings[3][0]['strike_price'] == 38.0
        assert wings[0][1:] == ('sell', 'open')
        assert wings[1][1:] == ('sell', 'open')
        assert wings[2][1:] == ('buy', 'open')
        assert wings[3][1:] == ('buy', 'open')

    def test_get_allocations(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000)
        oab = OptionAlphaTradingStrategy(pmb)
        assert oab._get_allocation(3) == 30_000
        assert oab._get_allocation(4.5) == 45_000

    def test_get_target_date(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-03-31', '%Y-%m-%d'))
        oab = OptionAlphaTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert oab._get_target_date({'timeline': [30, 60]}, options, 0) == '2019-05-03'
        assert oab._get_target_date({'timeline': [30, 60]}, options, 50) == '2019-05-17'
        assert oab._get_target_date({'timeline': [30, 60]}, options, 100) == '2019-05-17'

    def test_iron_condor(self):
        pmb = PaperMoneyBroker(account_id='test')
        oab = OptionAlphaTradingStrategy(pmb)
        wings = oab.iron_condor(strategies['iron_condor'], oa_options_1, width=1)
        assert wings[0][0]['strike_price'] == 42.0
        assert wings[1][0]['strike_price'] == 43.0
        assert wings[2][0]['strike_price'] == 36.5
        assert wings[3][0]['strike_price'] == 35.5
        assert wings[0][1:] == ('sell', 'open')
        assert wings[1][1:] == ('buy', 'open')
        assert wings[2][1:] == ('sell', 'open')
        assert wings[3][1:] == ('buy', 'open')

    def test_credit_spread(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        legs = oab.credit_spread(strategies['credit_spread'], oa_options_1, direction='bullish', width=3)
        assert legs[0][0]['strike_price'] == 38.5
        assert legs[0][1:] == ('sell', 'open')
        assert legs[1][0]['strike_price'] == 35.5
        assert legs[1][1:] == ('buy', 'open')

    def test_credit_spread_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        legs = oab.credit_spread(strategies['credit_spread'], oa_options_1, direction='bearish', width=4.5)
        assert legs[0][0]['strike_price'] == 40.0
        assert legs[0][1:] == ('sell', 'open')
        assert legs[1][0]['strike_price'] == 44.5
        assert legs[1][1:] == ('buy', 'open')

    def test_get_price_simple(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        legs = oab.credit_spread(strategies['credit_spread'], oa_options_1, direction='bearish', width=4.5)
        assert oab._get_price(legs) == 0.61 * 100

    def test_get_price_complex(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        wings = oab.iron_condor(strategies['iron_condor'], oa_options_1, width=1)
        assert oab._get_price(wings) == 0.155 * 100

    def test_make_trade_low_iv(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        oab = OptionAlphaTradingStrategy(pmb)
        with pytest.raises(TradeException):
            oab.make_trade('MU', 'neutral', 45)

    def test_make_trade_invalid_iv(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        oab = OptionAlphaTradingStrategy(pmb)
        with pytest.raises(TradeException):
            oab.make_trade('MU', 'neutral', 101)
        with pytest.raises(TradeException):
            oab.make_trade('MU', 'neutral', -1)

    def test_make_trade_invalid_allocation(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        oab = OptionAlphaTradingStrategy(pmb)
        with pytest.raises(TradeException):
            oab.make_trade('MU', 'neutral', 52, 21)
        with pytest.raises(TradeException):
            oab.make_trade('MU', 'neutral', 52, 0)

    def test_make_trade_invalid_direction(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        oab = OptionAlphaTradingStrategy(pmb)
        with pytest.raises(TradeException):
            oab.make_trade('MU', 'newtral', 52)

    def test_get_quantity(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        assert oab._get_quantity(30_000, 31) == 967

    def test_make_trade_neutral_mid_iv(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=oa_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        strategy, legs, q, p, _ = oab.make_trade('MU', 'neutral', 52)
        assert strategy == 'iron_condor'
        assert oab._get_price(legs) <= pmb.balance * 0.03
        assert legs[0][0]["strike_price"] == 42.0
        assert oab._get_price(legs) == 31.0
        assert q == 967
        assert p == 29_977

    def test_make_trade_neutral_high_iv(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=oa_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        strategy, legs, q, p, _ = oab.make_trade('MU', 'neutral', high_iv)
        assert strategy == 'iron_butterfly'
        assert oab._get_price(legs) <= pmb.balance * 0.03
        assert legs[0][0]["strike_price"] == 38.5
        assert q == 271
        assert round(p, ndigits=1) == 29_945.5

    def test_make_trade_bearish(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=oa_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        strategy, legs, q, p, _ = oab.make_trade('MU', 'bearish', high_iv)
        assert strategy == 'credit_spread'
        assert oab._get_price(legs) <= pmb.balance * 0.03
        assert legs[0][0]["strike_price"] == 40.0
        assert q == 540
        assert round(p) == 29_970

    def test_delete_position(self):
        name = 'oatrading-testdel'
        pmb = PaperMoneyBroker(account_id='testdel')
        test_id = str(uuid.uuid4())
        oab = OptionAlphaTradingStrategy(pmb)

        id_1 = str(uuid.uuid4())
        id_2 = str(uuid.uuid4())
        leg1 = "{}:leg:{}".format(name, id_1)
        leg2 = "{}:leg:{}".format(name, id_2)
        data = "{}:{}".format(name, test_id)
        positions = name + ":positions"
        legs = "{}:{}:legs".format(name, test_id)

        storage.hmset(data, {'test': 'testing'})
        storage.lpush(positions, test_id)
        storage.lpush(legs, id_1)
        storage.lpush(legs, id_2)
        storage.hmset(leg1, {'test': 'leg11'})
        storage.hmset(leg2, {'test': 'leg22'})
        oab._delete_position(test_id)
        assert not storage.exists(leg1,
                                  leg2,
                                  data,
                                  positions,
                                  legs)

    def test_storage(self):
        name = 'oatrading-teststor'
        pmb = PaperMoneyBroker(account_id='teststor', date=date, data=quotes, options_data=oa_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        _, _, quantity, price, oo = oab.make_trade('MU', 'bearish', high_iv)
        oid = oo["id"]
        assert oid == storage.lrange(name + ":positions", 0, -1)[0]
        data = storage.hgetall("{}:{}".format(name, oid))
        assert data['strategy'] == 'credit_spread'
        assert int(data['quantity']) == quantity
        assert float(data['price']) == price / quantity
        legs = storage.lrange("{}:{}:legs".format(name, oid), 0, -1)
        assert len(legs) == 2
        assert oo["legs"][0]["id"] in legs
        assert oo["legs"][1]["id"] in legs
        oab._delete_position(oid)

    def test_maintenance_no_action(self):
        name = 'testmaint-' + str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=date, data=quotes, options_data=oa_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        oab.make_trade('MU', 'bearish', high_iv)
        orders = oab.maintenance()
        assert not orders

    def test_maintenance_close(self):
        name = 'testmaint-' + str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=date, data=quotes, options_data=oa_options_1,
                               exp_dates=exp_dates)
        name = 'oatrading-' + name
        test_id = str(uuid.uuid4())
        id_1 = str(uuid.uuid4())
        id_2 = str(uuid.uuid4())
        leg1 = "{}:leg:{}".format(name, id_1)
        leg2 = "{}:leg:{}".format(name, id_2)
        data = "{}:{}".format(name, test_id)
        positions = name + ":positions"
        legs = "{}:{}:legs".format(name, test_id)

        storage.hmset(data, {'price': 112, 'quantity': 540, 'symbol': 'MU',
                             'strategy': 'credit_spread'})
        storage.lpush(positions, test_id)
        storage.lpush(legs, id_1)
        storage.lpush(legs, id_2)
        storage.hmset(leg1, {'option': 'https://api.robinhood.com/options/instruments/9d870f5d-bd44-4750-8ff6'
                                       '-7aee58249b9f/',
                             'side': 'sell',
                             'ratio_quantity': 1,
                             })
        storage.hmset(leg2, {'option': 'https://api.robinhood.com/options/instruments/388082d5-b1d9-404e-8aad'
                                       '-c92f40ee9ddb/',
                             'side': 'buy',
                             'ratio_quantity': 1,
                             })
        oab = OptionAlphaTradingStrategy(pmb)
        orders = oab.maintenance()
        assert len(orders) == 1
        assert len(orders[0]['legs']) == 2
        assert not storage.lrange(name + ":positions", 0, -1)
