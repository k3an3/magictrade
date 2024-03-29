import json
import os
import subprocess
import uuid
from datetime import datetime
from os.path import join, dirname
from typing import Dict
from unittest.mock import patch

import pytest
from data import quotes, rh_options_1, exp_dates, td_account_json, bad_options_1, \
    bad_options_2, ULTA_20_close, TSN_20_close, SHOP_20_close, rh_options_close, ma_20_data, quote_data

from magictrade import storage
from magictrade.broker import InsufficientFundsError, NonexistentAssetError, Broker
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.broker.robinhood import RHOption
from magictrade.broker.td_ameritrade import TDAmeritradeBroker, TDOption
from magictrade.datasource import DummyDataSource
from magictrade.runner import Runner
from magictrade.scripts.run_bollinger import check_signals as bb_check_signals
from magictrade.scripts.run_lin_slope import check_signals as ls_check_signals
from magictrade.scripts.run_lin_slope import get_n_sma
from magictrade.securities import InvalidOptionError, DummyOption
from magictrade.strategy import TradeConfigException, TradeDateException, TradeCriteriaException, NoTradeException, \
    TradingStrategy
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.longoption import LongOptionTradingStrategy
from magictrade.strategy.optionseller import OptionSellerTradingStrategy, strategies, TradeException, high_iv
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_account_history, get_percentage_change, get_allocation, calculate_percent_otm, \
    get_risk, from_date_format, find_option_with_probability, get_price_from_change

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
    def test_find_probability_call_short(self):
        pmb = PaperMoneyBroker(account_id='test', )
        calls = pmb.filter_options(rh_options_1, option_type='call')
        assert find_option_with_probability(calls, 70).id == '9d870f5d-bd44-4750-8ff6-7aee58249b9f'

    def test_find_probability_call_long(self):
        pmb = PaperMoneyBroker(account_id='test', )
        calls = pmb.filter_options(rh_options_1, option_type='call')
        assert find_option_with_probability(calls, 48).id == '03facad1-959d-4674-85d5-79d50ff75ea6'

    def test_find_probability_put_short(self):
        pmb = PaperMoneyBroker(account_id='test', )
        puts = pmb.filter_options(rh_options_1, option_type='put')
        assert find_option_with_probability(puts, 72).id == 'f3acdb4d-82da-417b-ad13-5255613745bd'

    def test_get_percentage_change(self):
        assert get_percentage_change(100, 200) == 100
        assert round(get_percentage_change(100, 100.57), 2) == 0.57
        assert get_percentage_change(100, 50) == -50

    def test_get_price_from_change(self):
        assert get_price_from_change(100, 100) == 200
        assert round(get_price_from_change(19.65, -25), 2) == 14.74
        assert get_price_from_change(100, -50) == 50

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


class TestOAStrategy:
    def test_get_long_leg_put(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='put')
        for option in puts:
            if option.strike_price == 38.5:
                short_leg = option
        assert osts._get_long_leg(puts, short_leg, 'put', width=1).strike_price == 37.5

    def test_get_long_leg_put_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='put')
        for option in puts:
            if option.strike_price == 38.5:
                short_leg = option
        assert osts._get_long_leg(puts, short_leg, 'put', width=2.5).strike_price == 36.0

    def test_get_long_leg_call(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='call')
        for option in puts:
            if option.strike_price == 38.0:
                short_leg = option
        assert osts._get_long_leg(puts, short_leg, 'call', width=1).strike_price == 39.0

    def test_get_long_leg_call_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        puts = pmb.filter_options(rh_options_1, option_type='call')
        for option in puts:
            if option.strike_price == 38.0:
                short_leg = option
        assert osts._get_long_leg(puts, short_leg, 'call', width=2.5).strike_price == 40.5

    def test_iron_butterfly(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        wings = osts.iron_butterfly(strategies['iron_butterfly'], rh_options_1, quote=39.5)
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
        osts = OptionSellerTradingStrategy(pmb)
        strategies['iron_butterfly']['probability'] = 75
        wings = osts.iron_butterfly(strategies['iron_butterfly'], rh_options_1, quote=39.5)
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
        osts = OptionSellerTradingStrategy(pmb)
        assert get_allocation(osts.broker, 3) == 30_000
        assert get_allocation(osts.broker, 4.5) == 45_000

    def test_get_target_date(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-03-31', '%Y-%m-%d'))
        osts = OptionSellerTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert osts._get_target_date({'timeline': [30, 60]}, options, 0, monthly=True) == '2019-04-19'
        assert osts._get_target_date({'timeline': [30, 60]}, options, 50) == '2019-05-17'
        assert osts._get_target_date({'timeline': [30, 60]}, options, 100) == '2019-05-17'

    def test_get_target_date_days_out(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-03-31', '%Y-%m-%d'))
        osts = OptionSellerTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert osts._get_target_date({'timeline': [30, 60]}, options, days_out=30) == '2019-05-03'
        assert osts._get_target_date({'timeline': [30, 60]}, options, days_out=45) == '2019-05-17'
        assert osts._get_target_date({'timeline': [30, 60]}, options, days_out=60) == '2019-05-17'

    def test_get_target_date_monthly(self):
        pmb = PaperMoneyBroker(account_id='test', balance=1_000_000, date=datetime.strptime('2019-11-24', '%Y-%m-%d'))
        osts = OptionSellerTradingStrategy(pmb)
        options = {'expiration_dates': exp_dates}
        assert osts._get_target_date({'timeline': [30, 60]}, options, days_out=30, monthly=True) == '2019-12-20'
        assert osts._get_target_date({'timeline': [30, 60]}, options, days_out=45, monthly=True) == '2020-01-17'
        assert osts._get_target_date({'timeline': [30, 60]}, options, days_out=60, monthly=True) == '2020-01-17'

    def test_iron_condor(self):
        pmb = PaperMoneyBroker(account_id='test')
        osts = OptionSellerTradingStrategy(pmb)
        wings = osts.iron_condor(strategies['iron_condor'], rh_options_1, width=1)
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
        osts = OptionSellerTradingStrategy(pmb)
        legs = osts.credit_spread(strategies['credit_spread'], rh_options_1, direction='bullish', width=3)
        assert legs[0][0].strike_price == 38.5
        assert legs[1][0].strike_price == 35.5
        assert legs[0][1] == 'sell'
        assert legs[1][1] == 'buy'

    def test_credit_spread_1(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        legs = osts.credit_spread(strategies['credit_spread'], rh_options_1, direction='bearish', width=4.5)
        assert legs[0][0].strike_price == 40.0
        assert legs[1][0].strike_price == 44.5
        assert legs[0][1] == 'sell'
        assert legs[1][1] == 'buy'

    def test_get_price_simple(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        legs = osts.credit_spread(strategies['credit_spread'], rh_options_1, direction='bearish', width=4.5)
        assert osts._get_price(legs) == 0.61

    def test_get_price_complex(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        wings = osts.iron_condor(strategies['iron_condor'], rh_options_1, width=1)
        assert osts._get_price(wings) == 0.155

    def test_make_trade_low_iv(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        osts = OptionSellerTradingStrategy(pmb)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'neutral', 45)

    def test_make_trade_invalid_iv(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        osts = OptionSellerTradingStrategy(pmb)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'neutral', 101)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'neutral', -1)

    def test_make_trade_invalid_allocation(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        osts = OptionSellerTradingStrategy(pmb)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'neutral', 52, 21)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'neutral', 52, 0)

    def test_make_trade_invalid_direction(self):
        pmb = PaperMoneyBroker(account_id='test', data=quotes)
        osts = OptionSellerTradingStrategy(pmb)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'newtral', 52)

    def test_get_quantity(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        assert osts._get_quantity(30_000, 3) == 100

    def test_get_quantity_price(self):
        pmb = PaperMoneyBroker(account_id='test', )
        osts = OptionSellerTradingStrategy(pmb)
        assert osts._get_quantity(30_000, 3, 1.56) == 208

    def test_make_trade_neutral_mid_iv(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        osts = OptionSellerTradingStrategy(pmb)
        result = osts.make_trade('MU', 'neutral', 52)
        assert result['strategy'] == 'iron_condor'
        assert len(result['legs']) == 4
        assert osts._get_price(result['legs']) <= pmb.balance * 0.03
        assert result['legs'][0][0].strike_price == 42.0
        assert osts._get_price(result['legs']) == 0.31
        assert result['quantity'] == 111
        assert result['price'] == 34.41

    def test_make_trade_neutral_high_iv(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        osts = OptionSellerTradingStrategy(pmb)
        result = osts.make_trade('MU', 'neutral', high_iv)
        assert result['strategy'] == 'iron_butterfly'
        assert len(result['legs']) == 4
        assert osts._get_price(result['legs']) <= pmb.balance * 0.03
        assert result['legs'][0][0].strike_price == 38.5
        assert result['quantity'] == 335
        assert round(result['price'], 2) == 370.17

    def test_make_trade_bearish(self):
        pmb = PaperMoneyBroker(account_id='test', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        osts = OptionSellerTradingStrategy(pmb)
        result = osts.make_trade('MU', 'bearish', high_iv)
        assert result['strategy'] == 'credit_spread'
        assert osts._get_price(result['legs']) <= pmb.balance * 0.03
        assert result['legs'][0][0].strike_price == 40.0
        assert result['quantity'] == 122
        assert round(result['price'], 2) == 67.71

    def test_delete_position(self):
        name = 'papermoney-testdel'
        pmb = PaperMoneyBroker(account_id='testdel')
        test_id = str(uuid.uuid4())
        osts = OptionSellerTradingStrategy(pmb)

        id_1 = str(uuid.uuid4())
        id_2 = str(uuid.uuid4())
        leg1 = "{}:leg:{}".format(name, id_1)
        leg2 = "{}:leg:{}".format(name, id_2)
        data = "{}:{}".format(name, test_id)
        positions = name + ":positions"
        legs = "{}:{}:legs".format(name, test_id)

        storage.hset(data, mapping={'test': 'testing'})
        storage.lpush(positions, test_id)
        storage.lpush(legs, id_1)
        storage.lpush(legs, id_2)
        storage.hset(leg1, mapping={'test': 'leg11'})
        storage.hset(leg2, mapping={'test': 'leg22'})
        osts.delete_position(test_id)
        assert not storage.exists(leg1,
                                  leg2,
                                  data,
                                  positions,
                                  legs)

    def test_storage(self):
        name = 'papermoney-teststor'
        pmb = PaperMoneyBroker(account_id='teststor', date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        osts = OptionSellerTradingStrategy(pmb)
        result = osts.make_trade('MU', 'bearish', high_iv)
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
        osts.delete_position(oid)

    def test_maintenance_no_action(self):
        name = str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        osts = OptionSellerTradingStrategy(pmb)
        osts.make_trade('MU', 'bearish', high_iv)
        orders = osts.maintenance()
        assert not orders

    def test_maintenance_close(self):
        name = str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=date, data=quotes, options_data=rh_options_1,
                               exp_dates=exp_dates)
        name = 'papermoney-' + name
        test_id = str(uuid.uuid4())
        id_1 = str(uuid.uuid4())
        id_2 = str(uuid.uuid4())
        leg1 = "{}:leg:{}".format(name, id_1)
        leg2 = "{}:leg:{}".format(name, id_2)
        data = "{}:{}".format(name, test_id)
        positions = name + ":positions"
        legs = "{}:{}:legs".format(name, test_id)

        storage.hset(data, mapping={'price': 112, 'quantity': 540, 'symbol': 'MU',
                                    'strategy': 'credit_spread'})
        storage.lpush(positions, test_id)
        storage.lpush(legs, id_1)
        storage.lpush(legs, id_2)
        storage.hset(leg1, mapping={'option': 'https://api.robinhood.com/options/instruments/9d870f5d-bd44-4750-8ff6'
                                              '-7aee58249b9f/',
                                    'side': 'sell',
                                    'ratio_quantity': 1,
                                    })
        storage.hset(leg2, mapping={'option': 'https://api.robinhood.com/options/instruments/388082d5-b1d9-404e-8aad'
                                              '-c92f40ee9ddb/',
                                    'side': 'buy',
                                    'ratio_quantity': 1,
                                    })
        osts = OptionSellerTradingStrategy(pmb)
        pmb.options = [
            {'option': 'https://api.robinhood.com/options/instruments/388082d5-b1d9-404e-8aad-c92f40ee9ddb/'},
            {'option': 'https://api.robinhood.com/options/instruments/9d870f5d-bd44-4750-8ff6-7aee58249b9f/'}]
        orders = osts.maintenance()
        assert len(orders) == 1
        assert len(orders[0].legs) == 2

    def test_trade_insufficient_balance(self):
        pmb = PaperMoneyBroker(account_id='test-balance', balance=50.0, date=date, data=quotes,
                               options_data=rh_options_1,
                               exp_dates=exp_dates)
        osts = OptionSellerTradingStrategy(pmb)
        with pytest.raises(NoTradeException):
            strategy, legs, q, p, _ = osts.make_trade('MU', 'bearish', high_iv)

    def test_get_fair_credit_vertical(self):
        pmb = PaperMoneyBroker()
        legs = [
            (DummyOption(probability_otm=0.70), 'sell'),
            (DummyOption(probability_otm=0.76), 'buy')
        ]
        assert round(OptionSellerTradingStrategy(pmb)._get_fair_credit(legs, 5), 2) == 1.5

    def test_get_fair_credit_iron_condor(self):
        pmb = PaperMoneyBroker()
        legs = [
            (DummyOption(probability_otm=0.85), 'sell'),
            (DummyOption(probability_otm=0.90), 'buy'),
            (DummyOption(probability_otm=0.86), 'sell'),
            (DummyOption(probability_otm=0.91), 'buy'),
        ]
        assert round(OptionSellerTradingStrategy(pmb)._get_fair_credit(legs, 3), 2) == 0.87

    def test_get_fair_credit_iron_condor_1(self):
        pmb = PaperMoneyBroker()
        legs = [
            (DummyOption(probability_otm=0.90), 'sell'),
            (DummyOption(probability_otm=0.95), 'buy'),
            (DummyOption(probability_otm=0.90), 'sell'),
            (DummyOption(probability_otm=0.95), 'buy'),
        ]
        assert round(OptionSellerTradingStrategy(pmb)._get_fair_credit(legs, 1), 2) == 0.2

    def test_make_trade_negative_credit(self):
        pmb = PaperMoneyBroker(account_id='test', date=from_date_format('2020-02-03'), data=quotes,
                               options_data=bad_options_1, exp_dates=['2020-03-20'])
        osts = OptionSellerTradingStrategy(pmb)
        with pytest.raises(TradeException):
            osts.make_trade('MU', 'bearish', 52, exp_date='2020-03-20')

    def test_maintenance_negative_price(self):
        name = 'testmaint-' + str(uuid.uuid4())
        pmb = PaperMoneyBroker(account_id=name, date=from_date_format('2020-02-03'), data=quotes,
                               options_data=bad_options_2, exp_dates=['2020-03-20'])
        osts = OptionSellerTradingStrategy(pmb)
        osts.make_trade('MU', 'bearish', high_iv, exp_date='2020-03-20')
        pmb.options_data = bad_options_1
        orders = osts.maintenance()
        assert not orders


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

    def test_calc_spread_width_butterfly(self):
        pmb = PaperMoneyBroker('test-balance')
        osts = OptionSellerTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 52, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 59, 'type': 'call'}), 'buy'),
            (RHOption({'strike_price': 52, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 47, 'type': 'put'}), 'buy'),
        )
        assert osts._calc_spread_width(legs) == 7

    def test_calc_spread_width_butterfly_1(self):
        pmb = PaperMoneyBroker('test-balance')
        osts = OptionSellerTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 52, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 59, 'type': 'call'}), 'buy'),
            (RHOption({'strike_price': 52, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 42, 'type': 'put'}), 'buy'),
        )
        assert osts._calc_spread_width(legs) == 10

    def test_calc_spread_width_iron_condor(self):
        pmb = PaperMoneyBroker('test-balance')
        osts = OptionSellerTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 64, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 65, 'type': 'call'}), 'buy'),
            (RHOption({'strike_price': 50, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 45, 'type': 'put'}), 'buy'),
        )
        assert osts._calc_spread_width(legs) == 5

    def test_calc_spread_width_iron_condor_1(self):
        pmb = PaperMoneyBroker('test-balance')
        osts = OptionSellerTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 100, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 110, 'type': 'call'}), 'buy'),
            (RHOption({'strike_price': 90, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 85, 'type': 'put'}), 'buy'),
        )
        assert osts._calc_spread_width(legs) == 10

    def test_calc_spread_width_vertical_call(self):
        pmb = PaperMoneyBroker('test-balance')
        osts = OptionSellerTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 100, 'type': 'call'}), 'sell'),
            (RHOption({'strike_price': 105, 'type': 'call'}), 'buy'),
        )
        assert osts._calc_spread_width(legs) == 5

    def test_calc_spread_width_vertical_put(self):
        pmb = PaperMoneyBroker('test-balance')
        osts = OptionSellerTradingStrategy(pmb)
        legs = (
            (RHOption({'strike_price': 105, 'type': 'put'}), 'sell'),
            (RHOption({'strike_price': 100, 'type': 'put'}), 'buy'),
        )
        assert osts._calc_spread_width(legs) == 5


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
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        calls = broker.filter_options(options_by_date, option_type='call')
        assert find_option_with_probability(calls, 70).id == 'SPY_120419C315'

    def test_find_probability_put_short(self, broker: TDAmeritradeBroker, options: Dict):
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        puts = broker.filter_options(options_by_date, option_type='put')
        assert find_option_with_probability(puts, 70).id == 'SPY_120419P308'

    def test_get_long_leg_put(self, broker: TDAmeritradeBroker, options: Dict):
        osts = OptionSellerTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        puts = broker.filter_options(options_by_date, option_type='put')
        for option in puts:
            if option.strike_price == 315.0:
                short_leg = option
        assert osts._get_long_leg(puts, short_leg, 'put', width=1).strike_price == 314.0

    def test_get_long_leg_put_1(self, broker: TDAmeritradeBroker, options: Dict):
        osts = OptionSellerTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        puts = broker.filter_options(options_by_date, option_type='put')
        for option in puts:
            if option.strike_price == 315.0:
                short_leg = option
        assert osts._get_long_leg(puts, short_leg, 'put', width=2.5).strike_price == 312.0

    def test_get_long_leg_call(self, broker: TDAmeritradeBroker, options: Dict):
        osts = OptionSellerTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        calls = broker.filter_options(options_by_date, option_type='call')
        for option in calls:
            if option.strike_price == 315.0:
                short_leg = option
        assert osts._get_long_leg(calls, short_leg, 'call', width=1).strike_price == 316.0

    def test_get_long_leg_call_1(self, broker: TDAmeritradeBroker, options: Dict):
        osts = OptionSellerTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        calls = broker.filter_options(options_by_date, option_type='call')
        for option in calls:
            if option.strike_price == 315.0:
                short_leg = option
        assert osts._get_long_leg(calls, short_leg, 'call', width=2.5).strike_price == 318.0

    def test_credit_spread(self, broker: TDAmeritradeBroker, options: Dict):
        osts = OptionSellerTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        legs = osts.credit_spread(strategies['credit_spread'], options_by_date, direction='bullish', width=3)
        assert legs[0][0].strike_price == 308.0
        assert legs[1][0].strike_price == 305.0
        assert legs[0][1] == 'sell'
        assert legs[1][1] == 'buy'

    def test_iron_condor(self, broker: TDAmeritradeBroker, options: Dict):
        osts = OptionSellerTradingStrategy(broker)
        options_by_date = broker.filter_options(options, ['2019-12-04'])
        wings = osts.iron_condor(strategies['iron_condor'], options_by_date, width=1)
        assert wings[0][0].strike_price == 318.0
        assert wings[1][0].strike_price == 319.0
        assert wings[2][0].strike_price == 302.0
        assert wings[3][0].strike_price == 301.0
        assert wings[0][1] == 'sell'
        assert wings[1][1] == 'buy'
        assert wings[2][1] == 'sell'
        assert wings[3][1] == 'buy'


class TestRunner:
    if not os.environ.get('SKIP_SLOW_TESTS') == "yes":
        def test_argparse(self):
            assert subprocess.run(['magictrade-daemon']).returncode == 2

        def test_lint(self):
            assert not subprocess.run(['pylint', '-E', 'magictrade']).returncode

    @pytest.fixture
    def trade_queue(self):
        storage.delete('test-runner-queue')
        return RedisTradeQueue('test-runner-queue')

    @pytest.fixture
    def identifier(self):
        return str(uuid.uuid4())

    def test_get_next_trade(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=23,
                                             hour=15,
                                             minute=13
                                         )),
                        None)
        trade = {'blah': 'abcdef', 'test_data': 'garbage'}
        identifier = str(uuid.uuid4())
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade()[0] == identifier

    def test_get_next_trade_before_start(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=23,
                                             hour=15,
                                             minute=14
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'start': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=15
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade() == (None, None)
        trade_queue.staged_to_queue()
        assert len(trade_queue) == 1

    def test_get_next_trade_after_start(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=23,
                                             hour=15,
                                             minute=15
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'start': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=15
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade()[0] == identifier

    def test_get_next_trade_before_end(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=22,
                                             hour=14,
                                             minute=15
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'end': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=00
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade()[0] == identifier

    def test_get_next_trade_after_end(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=24,
                                             hour=9,
                                             minute=45
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'end': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=00
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade() == (None, None)

    def test_get_next_trade_before_start_end(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=23,
                                             hour=9,
                                             minute=30
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'start': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=15
                 ).timestamp(),
                 'end': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=16,
                     minute=00
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade() == (None, None)

    def test_get_next_trade_after_start_end(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=24,
                                             hour=9,
                                             minute=30
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'start': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=15
                 ).timestamp(),
                 'end': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=16,
                     minute=00
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade() == (None, None)

    def test_get_next_trade_inside_start_end(self, trade_queue, identifier):
        runner = Runner(None, trade_queue,
                        PaperMoneyBroker('test-runner',
                                         date=datetime(
                                             year=2020,
                                             month=1,
                                             day=23,
                                             hour=15,
                                             minute=30
                                         )),
                        None)
        trade = {'blah': 'abcde', 'test_data': 'garbage',
                 'start': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=15,
                     minute=15
                 ).timestamp(),
                 'end': datetime(
                     year=2020,
                     month=1,
                     day=23,
                     hour=16,
                     minute=00
                 ).timestamp()}
        trade_queue.add(identifier, trade)
        assert runner.get_next_trade()[0] == identifier


class TestBB:
    @pytest.fixture
    def broker(self):
        return PaperMoneyBroker()

    @pytest.fixture
    def bbts(self, broker):
        dds = DummyDataSource({'history': {}})
        return OptionSellerTradingStrategy(broker, dds)

    def test_check_signal_1(self, bbts):
        # TODO: test currently fails, but may be right? odd.
        assert bb_check_signals(ULTA_20_close) == (True, False, False)

    def test_check_signal_2(self, bbts):
        assert bb_check_signals(TSN_20_close) == (False, True, False)

    def test_check_signal_3(self, bbts):
        assert bb_check_signals(SHOP_20_close) == (False, False, True)

    def test_calc_risk_reward(self, bbts):
        assert round(TradingStrategy._calc_risk_reward(0.30, 1), 2) == 0.43
        assert round(TradingStrategy._calc_risk_reward(1.80, 5), 2) == 0.56

    def test_calc_rr_over_delta(self, bbts):
        assert round(TradingStrategy._calc_rr_over_delta(0.42, 0.3), 2) == 1.40
        assert round(TradingStrategy._calc_rr_over_delta(0.25, 0.25), 2) == 1.00


class TestNewCore:
    @pytest.fixture
    def strategy(self):
        return OptionSellerTradingStrategy(PaperMoneyBroker(date='2019-02-22', data=quotes, options_data=rh_options_1,
                                                            exp_dates=exp_dates))

    def test_custom_trade(self, strategy):
        p = strategy.make_trade('MU', direction='put', days_out=35, sort_reverse=True, spread_width=1, sort_by='delta',
                                leg_criteria='20 < abs(delta) * 100 and abs(delta) * 100 < 30.9')
        assert p['status'] == 'placed'
        assert p['quantity'] == 375
        assert round(p['price'], 2) == 75.00
        assert p['legs'][0][0]['strike_price'] == 38.00
        assert p['legs'][1][0]['strike_price'] == 37.00

    def test_custom_trade_close(self, strategy):
        p = strategy.make_trade('MU', direction='put', sort_reverse=True, days_out=35, spread_width=1, sort_by='delta',
                                leg_criteria='20 < abs(delta) * 100 and abs(delta) * 100 < 30.9',
                                close_criteria=["value and -1 * change >= 50"])
        for leg in p['order'].legs:
            strategy.broker.options[leg['id']] = leg
        strategy.broker.options_data = rh_options_close
        strategy.broker.date = '2019-02-23'
        m = strategy.maintenance()
        assert len(m)


class TestLinReg:
    def test_get_n_sma(self):
        assert [round(n, 2) for n in get_n_sma(quote_data, len(ma_20_data), 20)] == ma_20_data

    def test_signal(self):
        assert ls_check_signals(quote_data[-1], quote_data, 5, 20)

    def test_signal_(self):
        assert ls_check_signals(quote_data[-1], quote_data, 5, 10)

    def test_signal_false(self):
        assert not ls_check_signals(quote_data[-1], list(reversed(quote_data)), 5, 10)
