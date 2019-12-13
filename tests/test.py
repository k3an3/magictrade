import json
import uuid
from datetime import datetime
from os.path import join, dirname
from typing import Dict
from unittest.mock import patch

import pytest
from data import quotes, human_quotes_1, reactive_quotes, rh_options_1, exp_dates, td_account_json

from magictrade import storage
from magictrade.broker import InsufficientFundsError, NonexistentAssetError, InvalidOptionError, Broker
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.broker.robinhood import RHOption
from magictrade.broker.td_ameritrade import TDAmeritradeBroker, TDOption
from magictrade.strategy import TradeConfigException, TradeDateException, TradeCriteriaException
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy, DEFAULT_CONFIG
from magictrade.strategy.longoption import LongOptionTradingStrategy
from magictrade.strategy.optionalpha import OptionAlphaTradingStrategy, strategies, TradeException, high_iv
from magictrade.strategy.reactive import ReactiveStrategy
from magictrade.utils import get_account_history, get_percentage_change, get_allocation, calculate_percent_otm, get_risk

date = datetime.strptime("2019-03-31", "%Y-%m-%d")


class TestRunner:
    def test_handle_results(self):
        pass

    def test_handle_results_deferred(self):
        pass


class TestPaperMoneyBroker:
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

    def test_filter_option_type_call(self):
        pmb = PaperMoneyBroker(account_id='test', )
        for option in pmb.filter_options(rh_options_1, option_type='call'):
            assert option.option_type == 'call'

    def test_filter_option_type_put(self):
        pmb = PaperMoneyBroker(account_id='test', )
        for option in pmb.filter_options(rh_options_1, option_type='put'):
            assert option.option_type == 'put'

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

    def test_prob_otm(self):
        assert calculate_percent_otm(311.79, 313, 7.45, 4) == 0.69
        assert calculate_percent_otm(311.79, 308, 7.30, 4) == 0.95

    def test_get_risk(self):
        assert get_risk(3, 1.12) == 188

    def test_get_risk_1(self):
        assert get_risk(5, 2.50) == 250


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
    def test_find_probability_call_short(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        calls = pmb.filter_options(rh_options_1, option_type='call')
        assert oab._find_option_with_probability(calls, 70, 'short').id == '9d870f5d-bd44-4750-8ff6-7aee58249b9f'

    def test_find_probability_call_long(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        calls = pmb.filter_options(rh_options_1, option_type='call')
        assert oab._find_option_with_probability(calls, 48, 'long').id == '03facad1-959d-4674-85d5-79d50ff75ea6'

    def test_find_probability_put_short(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='put')
        assert oab._find_option_with_probability(puts, 72, 'short').id == 'f3acdb4d-82da-417b-ad13-5255613745bd'

    def test_get_long_leg_put(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='put')
        for option in puts:
            if option.strike_price == 38.5:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'put', width=1).strike_price == 37.5

    def test_get_long_leg_put_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='put')
        for option in puts:
            if option.strike_price == 38.5:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'put', width=2.5).strike_price == 36.0

    def test_get_long_leg_call(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='call')
        for option in puts:
            if option.strike_price == 38.0:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'call', width=1).strike_price == 39.0

    def test_get_long_leg_call_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='call')
        for option in puts:
            if option.strike_price == 38.0:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'call', width=2.5).strike_price == 40.5

    def test_iron_butterfly(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        wings = oab.iron_butterfly(strategies['iron_butterfly'], rh_options_1, quote=39.5)
        assert wings[0][0].strike_price == 39.5
        assert wings[1][0].strike_price == 39.5
        assert wings[2][0].strike_price == 42.0
        assert wings[3][0].strike_price == 36.5
        assert wings[0][1] == 'sell'
        assert wings[1][1] == 'sell'
        assert wings[2][1] == 'buy'
        assert wings[3][1] == 'buy'

    def test_iron_butterfly_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        strategies['iron_butterfly']['probability'] = 75
        wings = oab.iron_butterfly(strategies['iron_butterfly'], rh_options_1, quote=39.5)
        assert wings[0][0].strike_price == 39.5
        assert wings[1][0].strike_price == 39.5
        assert wings[2][0].strike_price == 40.5
        assert wings[3][0].strike_price == 38.0
        assert wings[0][1] == 'sell'
        assert wings[1][1] == 'sell'
        assert wings[2][1] == 'buy'
        assert wings[3][1] == 'buy'

    def test_get_allocations(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000)
        oab = OptionAlphaTradingStrategy(pmb)
        assert get_allocation(oab.broker, 3) == 30_000
        assert get_allocation(oab.broker, 4.5) == 45_000

    def test_get_target_date(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-03-31', '%Y-%m-%d'))
        oab = OptionAlphaTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert oab._get_target_date({'timeline': [30, 60]}, options, 0) == '2019-04-19'
        assert oab._get_target_date({'timeline': [30, 60]}, options, 50) == '2019-05-17'
        assert oab._get_target_date({'timeline': [30, 60]}, options, 100) == '2019-05-17'

    def test_get_target_date_days_out(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-03-31', '%Y-%m-%d'))
        oab = OptionAlphaTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert oab._get_target_date({'timeline': [30, 60]}, options, days_out=30) == '2019-05-03'
        assert oab._get_target_date({'timeline': [30, 60]}, options, days_out=45) == '2019-05-17'
        assert oab._get_target_date({'timeline': [30, 60]}, options, days_out=60) == '2019-05-17'

    def test_get_target_date_monthly(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-11-24', '%Y-%m-%d'))
        oab = OptionAlphaTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert oab._get_target_date({'timeline': [30, 60]}, options, days_out=30, monthly=True) == '2019-12-20'
        assert oab._get_target_date({'timeline': [30, 60]}, options, days_out=45, monthly=True) == '2020-01-17'
        assert oab._get_target_date({'timeline': [30, 60]}, options, days_out=60, monthly=True) == '2020-01-17'

    def test_iron_condor(self):
        pmb = PaperMoneyBroker(account_id='test')
        oab = OptionAlphaTradingStrategy(pmb)
        wings = oab.iron_condor(strategies['iron_condor'], rh_options_1, width=1)
        assert wings[0][0].strike_price == 42.0
        assert wings[1][0].strike_price == 43.0
        assert wings[2][0].strike_price == 36.5
        assert wings[3][0].strike_price == 35.5
        assert wings[0][1] == 'sell'
        assert wings[1][1] == 'buy'
        assert wings[2][1] == 'sell'
        assert wings[3][1] == 'buy'

    def test_credit_spread(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        legs = oab.credit_spread(strategies['credit_spread'], rh_options_1, direction='bullish', width=3)
        assert legs[0][0].strike_price == 38.5
        assert legs[1][0].strike_price == 35.5
        assert legs[0][1] == 'sell'
        assert legs[1][1] == 'buy'

    def test_credit_spread_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        legs = oab.credit_spread(strategies['credit_spread'], rh_options_1, direction='bearish', width=4.5)
        assert legs[0][0].strike_price == 40.0
        assert legs[1][0].strike_price == 44.5
        assert legs[0][1] == 'sell'
        assert legs[1][1] == 'buy'

    def test_get_price_simple(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        legs = oab.credit_spread(strategies['credit_spread'], rh_options_1, direction='bearish', width=4.5)
        assert oab._get_price(legs) == 0.61

    def test_get_price_complex(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        wings = oab.iron_condor(strategies['iron_condor'], rh_options_1, width=1)
        assert oab._get_price(wings) == 0.155

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
        assert oab._get_quantity(30_000, 3) == 100

    def test_get_quantity_price(self):
        pmb = PaperMoneyBroker(account_id='test', )
        oab = OptionAlphaTradingStrategy(pmb)
        assert oab._get_quantity(30_000, 3, 1.56) == 208

    def test_make_trade_neutral_mid_iv(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        result = oab.make_trade('MU', 'neutral', 52)
        assert result['strategy'] == 'iron_condor'
        assert oab._get_price(result['legs']) <= pmb.balance * 0.03
        assert result['legs'][0][0].strike_price == 42.0
        assert oab._get_price(result['legs']) == 0.31
        assert result['quantity'] == 111
        assert result['price'] == 34.41

    def test_make_trade_neutral_high_iv(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        result = oab.make_trade('MU', 'neutral', high_iv)
        assert result['strategy'] == 'iron_butterfly'
        assert oab._get_price(result['legs']) <= pmb.balance * 0.03
        assert result['legs'][0][0].strike_price == 38.5
        assert result['quantity'] == 335
        assert round(result['price'], 2) == 370.17

    def test_make_trade_bearish(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        result = oab.make_trade('MU', 'bearish', high_iv)
        assert result['strategy'] == 'credit_spread'
        assert oab._get_price(result['legs']) <= pmb.balance * 0.03
        assert result['legs'][0][0].strike_price == 40.0
        assert result['quantity'] == 122
        assert round(result['price'], 2) == 67.71

    def test_delete_position(self):
        name = 'optionalpha-testdel'
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
        oab.delete_position(test_id)
        assert not storage.exists(leg1,
                                  leg2,
                                  data,
                                  positions,
                                  legs)

    def test_storage(self):
        name = 'optionalpha-teststor'
        pmb = PaperMoneyBroker(account_id='teststor', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        result = oab.make_trade('MU', 'bearish', high_iv)
        oid = result['order'].id
        assert oid == storage.lrange(name + ":positions", 0, -1)[0]
        data = storage.hgetall("{}:{}".format(name, oid))
        assert data['strategy'] == 'credit_spread'
        assert int(data['quantity']) == result['quantity']
        assert float(data['price']) == result['price'] / result['quantity']
        legs = storage.lrange("{}:{}:legs".format(name, oid), 0, -1)
        assert len(legs) == 2
        assert result['order'].legs[0]["id"] in legs
        assert result['order'].legs[1]["id"] in legs
        oab.delete_position(oid)

    def test_maintenance_no_action(self):
        name = 'testmaint-' + str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        oab.make_trade('MU', 'bearish', high_iv)
        orders = oab.maintenance()
        assert not orders

    def test_maintenance_close(self):
        name = 'testmaint-' + str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        name = 'optionalpha-' + name
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
        pmb.options = [
            {'option': 'https://api.robinhood.com/options/instruments/388082d5-b1d9-404e-8aad-c92f40ee9ddb/'},
            {'option': 'https://api.robinhood.com/options/instruments/9d870f5d-bd44-4750-8ff6-7aee58249b9f/'}]
        orders = oab.maintenance()
        assert len(orders) == 1
        assert len(orders[0].legs) == 2
        assert not storage.lrange(name + ":positions", 0, -1)

    def test_trade_insufficient_balance(self):
        pmb = PaperMoneyBroker(account_id='test-balance', balance=50.0, date=date, data=quotes,
                               options_data=rh_options_1,
                               exp_dates=exp_dates)
        oab = OptionAlphaTradingStrategy(pmb)
        with pytest.raises(TradeException):
            strategy, legs, q, p, _ = oab.make_trade('MU', 'bearish', high_iv)


class TestLongOption:
    def test_config_validation(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        # Option type
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'puts', 1, '2019-10-02', 1)
        # Invalid date
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, 'aBCd-10-02', 1)
        # Invalid date
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '201910-02', 1)
        # Invalid date
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-2', 1)
        # Invalid strike
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', -2, '2019-10-02', 1)
        # Invalid allocation pct
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', -1)
        # Invalid allocation pct
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', 100.01)
        # Invalid allocation dollars
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', allocation_dollars=-1)
        # Double allocation
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', 1, 1)
        # Invalid days out
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', 1, days_out=-1)
        with pytest.raises(TradeConfigException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', 1, days_out=10000)

    def test_trade_validation(self):
        pmb = PaperMoneyBroker(data=quotes, options_data={'ignored': None})
        lots = LongOptionTradingStrategy(pmb)
        # No quote
        with pytest.raises(TradeException):
            lots.make_trade('TST', 'put', 1, '2019-10-02', 1)
        # No options with date
        pmb = PaperMoneyBroker(data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        with pytest.raises(TradeException):
            lots.make_trade('MU', 'put', 1, '2019-10-02', 1)
        # No option with strike
        with pytest.raises(TradeException):
            lots.make_trade('SPY', 'put', 1000, '2019-10-02', 1)

    def test_zero_quantity(self):
        pmb = PaperMoneyBroker(data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        # Quantity equals zero with insufficient allocation
        with pytest.raises(TradeException):
            lots.make_trade('MU', 'put', 31, '2019-04-05', allocation_dollars=1)
        # Quantity equals zero with insufficient allocation
        with pytest.raises(TradeException):
            lots.make_trade('MU', 'put', 31, '2019-04-05', 0.0001)

    def test_find_option(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        option = lots.find_option(rh_options_1, 35.00)
        assert option['id'] == 'd9ae1f75-2aa5-4cea-9c97-f14da4f9dd1d'

    def test_get_option(self):
        pmb = PaperMoneyBroker(data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        option = lots.get_option('MU', 'put', '2019-04-05', 35)
        assert option['id'] == 'd9ae1f75-2aa5-4cea-9c97-f14da4f9dd1d'
        option = lots.get_option('MU', 'call', '2019-04-05', 44)
        assert option['id'] == 'b389f415-bd3e-4eb7-9e8d-90baf8881053'

    def test_trade(self):
        pmb = PaperMoneyBroker(data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        trade = lots.make_trade('MU', 'call', 42.5, '2019-04-05', allocation_dollars=400)
        assert trade == {'status': 'placed', 'quantity': 1, 'price': 327.50}

    def test_trade_days_out(self):
        pmb = PaperMoneyBroker(date=datetime.strptime('2019-03-29', '%Y-%m-%d'),
                               data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        trade = lots.make_trade('MU', 'call', 42.5, days_out=7, allocation_dollars=400)
        assert trade == {'status': 'placed', 'quantity': 1, 'price': 327.50}

    def test_trade_days_fuzzy(self):
        pmb = PaperMoneyBroker(date=datetime.strptime('2019-03-29', '%Y-%m-%d'),
                               data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        trade = lots.make_trade('MU', 'call', 42.5, days_out=9, allocation_dollars=400)
        assert trade == {'status': 'placed', 'quantity': 1, 'price': 327.50}

    def test_trade_days_fuzzy_too_far(self):
        pmb = PaperMoneyBroker(date=datetime.strptime('2019-03-29', '%Y-%m-%d'),
                               data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        with pytest.raises(TradeDateException):
            lots.make_trade('MU', 'call', 42.5, days_out=50, allocation_dollars=400)

    def test_make_trade_criteria_valid(self):
        pmb = PaperMoneyBroker(data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        trade = lots.make_trade('MU', 'call', 42.5, '2019-04-05', allocation_dollars=700,
                                open_criteria=[
                                    {
                                        'expr': 'price < 39.21',
                                    }
                                ])
        assert trade == {'status': 'placed', 'quantity': 2, 'price': 327.50}

    def test_make_trade_criteria_defer(self):
        pmb = PaperMoneyBroker(data=quotes, options_data=rh_options_1)
        lots = LongOptionTradingStrategy(pmb)
        trade = lots.make_trade('MU', 'call', 42.5, '2019-04-05', allocation_dollars=700,
                                open_criteria=[
                                    {
                                        'expr': 'price > 39.21',
                                    }
                                ])
        assert trade == {'status': 'deferred'}


class TestTradingStrategyBase:
    def test_criteria_missing_args(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        with pytest.raises(TradeCriteriaException):
            lots.evaluate_criteria(criteria=[
                {
                    'expr': 'price < 40.00',
                }
            ])

    def test_criteria_valid_price(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 40.00',
            }
        ], price=38.64)

    def test_criteria_invalid_price(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert not lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 40.00',
            }
        ], price=40.01)

    def test_criteria_valid_price_and(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 40.00',
            },
            {
                'expr': 'price > 36.00',
            }
        ], price=38.64)

    def test_criteria_valid_price_and_1(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 45.00',
            },
            {
                'expr': 'price % 2 < 1'
            },
            {
                'expr': 'price == 38.64'
            }
        ], price=38.64)

    def test_criteria_invalid_price_and(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert not lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 40.00'
            },
            {
                'expr': 'price > 39.00'
            }
        ], price=38.64)

    def test_criteria_invalid_price_and_1(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert not lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 40.00'
            },
            {
                'expr': 'price > 39.00'
            },
            {
                'expr': 'price % 2 < 1'
            },
        ], price=38.64)

    def test_criteria_valid_price_or_all(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 40.00'
            },
            {
                'expr': 'price > 38.00',
                'operation': 'or',
            },
        ], price=38.64)

    def test_criteria_valid_price_or(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 36.00'
            },
            {
                'expr': 'price > 38.00',
                'operation': 'or',
            },
        ], price=38.64)

    def test_criteria_invalid_price_or(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert not lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 36.00'
            },
            {
                'expr': 'price > 39.00',
                'operation': 'or',
            },
        ], price=38.64)

    def test_criteria_valid_price_complex(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 36.00'
            },
            {
                'expr': 'price > 39.00',
                'operation': 'and',
            },
            {
                'expr': 'price % 2 < 1',
                'operation': 'or',
            }
        ], price=38.64)

    def test_criteria_invalid_price_complex(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        assert not lots.evaluate_criteria(criteria=[
            {
                'expr': 'price < 36.00'
            },
            {
                'expr': 'price > 39.00',
                'operation': 'and',
            },
            {
                'expr': 'price % 2 >= 1',
                'operation': 'or',
            }
        ], price=38.64)

    def test_criteria_valid_date(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        current_time = datetime.strptime('2019-10-20 12:00', '%Y-%m-%d %H:%M')
        trade_time = datetime.strptime('2019-10-20 09:30', '%Y-%m-%d %H:%M')
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'date >= ' + str(trade_time.timestamp())
            },
        ], date=current_time.timestamp())

    def test_criteria_invalid_date(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        current_time = datetime.strptime('2019-10-20 12:00', '%Y-%m-%d %H:%M')
        trade_time = datetime.strptime('2019-10-20 15:30', '%Y-%m-%d %H:%M')
        assert not lots.evaluate_criteria(criteria=[
            {
                'expr': 'date >= ' + str(trade_time.timestamp())
            },
        ], date=current_time.timestamp())

    def test_criteria_valid_date_price(self):
        pmb = PaperMoneyBroker()
        lots = LongOptionTradingStrategy(pmb)
        current_time = datetime.strptime('2019-10-20 12:00', '%Y-%m-%d %H:%M')
        trade_time = datetime.strptime('2019-10-20 11:30', '%Y-%m-%d %H:%M')
        assert lots.evaluate_criteria(criteria=[
            {
                'expr': 'date >= ' + str(trade_time.timestamp())
            },
            {
                'expr': 'price < 200'
            }
        ], price=100, date=current_time.timestamp())

    def test_butterfly_spread_width(self):
        pmb = PaperMoneyBroker('test-balance')
        oab = OptionAlphaTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 52, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 59, 'type': 'call'}), 'buy'),
            (RHOption({'strike_price': 52, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 47, 'type': 'put'}), 'buy'),
        )
        assert oab._butterfly_spread_width(legs) == 7

    def test_butterfly_spread_width_1(self):
        pmb = PaperMoneyBroker('test-balance')
        oab = OptionAlphaTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 52, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 59, 'type': 'call'}), 'buy'),
            (RHOption({'strike_price': 52, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 42, 'type': 'put'}), 'buy'),
        )
        assert oab._butterfly_spread_width(legs) == 10


class TestBroker:
    def test_parse_leg(self):
        leg = {'side': 'buy'}
        assert Broker.parse_leg(leg) == (leg, 'buy')

    def test_parse_leg_1(self):
        leg = ({'leg': 'leg'}, 'buy')
        assert Broker.parse_leg(leg) == (leg[0], 'buy')


class TestRobinhoodBroker:
    pass


class TestTDAmeritradeBroker:
    @pytest.fixture
    def broker(self):
        with patch('requests.request') as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = td_account_json
            return TDAmeritradeBroker(client_id='asdf', account_id='<accountno>', access_token='access',
                                      refresh_token='refresh')

    @pytest.fixture
    def options(self, broker: TDAmeritradeBroker):
        with open(join(dirname(__file__), 'data', 'td_ameritrade_spy_options.json')) as f:
            raw_options = json.load(f)
        with patch('requests.request') as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = raw_options
            return broker.get_options('SPY')

    def test_options(self, broker: TDAmeritradeBroker, options: Dict):
        assert '2019-12-04' in options['expiration_dates']
        assert len(options['put']) == 36
        assert len(options['call']) == 36

    def test_balance(self, broker: TDAmeritradeBroker):
        with patch('requests.request') as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = td_account_json['<accountno>']
            assert broker.balance == 2729.96

    def test_buying_power(self, broker: TDAmeritradeBroker):
        with patch('requests.request') as m:
            m.return_value.status_code = 200
            m.return_value.json.return_value = td_account_json['<accountno>']
            assert broker.buying_power == 1980.97

    def test_filter_options_date(self, broker: TDAmeritradeBroker, options: Dict):
        filtered = broker.filter_options(options, ['2019-12-04'])
        assert len(filtered['call']) == 53
        assert len(filtered['put']) == 53

    def test_mark_price(self):
        assert TDOption({'mark': 150}).mark_price == 150

    def test_filter_options_type_puts(self, broker: TDAmeritradeBroker, options: Dict):
        filtered = broker.filter_options(options, ['2019-12-23'])
        filtered = broker.filter_options(filtered, option_type='put')
        assert len(filtered) == 23
        for option in filtered:
            assert option.option_type == 'put'

    def test_filter_options_type_calls(self, broker: TDAmeritradeBroker, options: Dict):
        filtered = broker.filter_options(options, ['2019-12-31'])
        filtered = broker.filter_options(filtered, option_type='call')
        assert len(filtered) == 124
        for option in filtered:
            assert option.option_type == 'call'

    def test_options_transact_invalid(self, broker: TDAmeritradeBroker):
        with pytest.raises(InvalidOptionError):
            broker.options_transact([], None, 0.0, 1, 'buy')

    def test_find_probability_call_short(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        calls = broker.filter_options(options_by_date, option_type='call')
        assert oab._find_option_with_probability(calls, 70, 'short').id == 'SPY_120419C315'

    def test_find_probability_put_short(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        puts = broker.filter_options(options_by_date, option_type='put')
        assert oab._find_option_with_probability(puts, 70, 'short').id == 'SPY_120419P308'

    def test_get_long_leg_put(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        puts = broker.filter_options(options_by_date, option_type='put')
        for option in puts:
            if option.strike_price == 315.0:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'put', width=1).strike_price == 314.0

    def test_get_long_leg_put_1(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        puts = broker.filter_options(options_by_date, option_type='put')
        for option in puts:
            if option.strike_price == 315.0:
                short_leg = option
        assert oab._get_long_leg(puts, short_leg, 'put', width=2.5).strike_price == 312.0

    def test_get_long_leg_call(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        calls = broker.filter_options(options_by_date, option_type='call')
        for option in calls:
            if option.strike_price == 315.0:
                short_leg = option
        assert oab._get_long_leg(calls, short_leg, 'call', width=1).strike_price == 316.0

    def test_get_long_leg_call_1(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        calls = broker.filter_options(options_by_date, option_type='call')
        for option in calls:
            if option.strike_price == 315.0:
                short_leg = option
        assert oab._get_long_leg(calls, short_leg, 'call', width=2.5).strike_price == 318.0

    def test_credit_spread(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        legs = oab.credit_spread(strategies['credit_spread'], options_by_date, direction='bullish', width=3)
        assert legs[0][0].strike_price == 308.0
        assert legs[1][0].strike_price == 305.0
        assert legs[0][1] == 'sell'
        assert legs[1][1] == 'buy'

    def test_iron_condor(self, broker: TDAmeritradeBroker, options: Dict):
        oab = OptionAlphaTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        wings = oab.iron_condor(strategies['iron_condor'], options_by_date, width=1)
        assert wings[0][0].strike_price == 318.0
        assert wings[1][0].strike_price == 319.0
        assert wings[2][0].strike_price == 302.0
        assert wings[3][0].strike_price == 301.0
        assert wings[0][1] == 'sell'
        assert wings[1][1] == 'buy'
        assert wings[2][1] == 'sell'
        assert wings[3][1] == 'buy'
