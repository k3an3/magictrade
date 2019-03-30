from datetime import datetime, timedelta
from typing import List, Dict

from time import strftime

from magictrade import Broker
from magictrade.strategy import TradingStrategy

strategies = {
    'iron_condor': {
        'timeline': [30, 60],
        'target': 50,
        'probability': 85,
    },
    'iron_butterfly': {
        'timeline': [30, 60],
        'target': 25,
        'probability': 85
    },
    'credit_spread': {
        'timeline': [30, 60],
        'target': 50,
        'probability': 70
    },
}

high_iv = 75

valid_directions = ('neutral', 'bullish', 'bearish')


class OptionAlphaTradingStrategy(TradingStrategy):
    def __init__(self, broker: Broker):
        self.broker = broker

    @staticmethod
    def _find_option_with_probability(options: List, probability: int, ttype: str = 'short'):
        key = 'chance_of_profit_' + ttype
        options = [o for o in options if o[key] is not None]
        for option in sorted(options, key=lambda o: o[key]):
            if option[key] * 100 >= probability:
                return option

    @staticmethod
    def _filter_option_type(options: List, o_type: str):
        return list(filter(lambda x: x["type"] == o_type, options))

    @staticmethod
    def _get_long_leg(options: List, short_leg: Dict, o_type: str):
        match = 100
        while match > 50:
            for option in sorted(options, key=lambda o: o['strike_price']):
                if o_type == 'call' and option['strike_price'] > short_leg['strike_price'] \
                        or o_type == 'put' and option['strike_price'] < short_leg['strike_price']:
                    distance = abs(option['strike_price'] - short_leg['strike_price'])
                    if distance >= 1:
                        # This calculation might be superfluous. Maybe increase minmatch to make it worth it?
                        if short_leg['mark_price'] - option['mark_price'] >= distance * short_leg['chance_of_profit_long'] * match / 100:
                            return option
            match -= 1

    def iron_butterfly(self, config: Dict, symbol: str, quote: float, options: List, direction: str):
        calls = self._filter_option_type(options, 'call')
        puts = self._filter_option_type(options, 'put')
        closest_call = [c for c in sorted(calls, key=lambda o: o['strike_price']) if c['strike_price'] >= quote][0]
        for option in puts:
            if option['strike_price'] == closest_call['strike_price']:
                closest_put = option
        call_wing = self._find_option_with_probability(calls, config['probability'])
        put_wing = self._find_option_with_probability(puts, config['probability'])
        return (closest_call, 'sell', 'open'), (closest_put, 'sell', 'open'), \
               (call_wing, 'buy', 'open'), (put_wing, 'buy', 'open')

    def iron_condor(self, config: Dict, symbol: str, quote: float, options: List, direction: str):
        call_wing = self.credit_spread(config, symbol, quote, self._filter_option_type(options, 'call'), 'bearish')
        put_wing = self.credit_spread(config, symbol, quote, self._filter_option_type(options, 'put'), 'bullish')
        return call_wing[0], call_wing[1], put_wing[0], put_wing[1]

    def credit_spread(self, config: Dict, symbol: str, quote: float, options: List, direction: str):
        if direction == 'bullish':
            o_type = 'put'
        else:
            o_type = 'call'
        options = self._filter_option_type(options, o_type)
        short_leg = self._find_option_with_probability(options, config['probability'])
        long_leg = self._get_long_leg(options, short_leg, o_type)
        return (short_leg, 'sell', 'open'), (long_leg, 'buy', 'open')

    def make_trade(self, symbol: str, direction: str, iv_rank: int = 50, allocation: int = 3, timeline: int = 50):
        q = self.broker.get_quote()

        if direction not in valid_directions:
            raise Exception("Invalid direction. Must be in " + str(valid_directions))

        if not 0 <= iv_rank <= 100:
            raise Exception("Invalid iv_rank.")

        if not 0 < allocation < 20:
            raise Exception("Invalid allocation amount or crazy.")

        if not iv_rank >= 50:
            raise Exception("iv_rank too low.")
        elif direction == 'neutral':
            if iv_rank > high_iv:
                method = self.iron_butterfly
                strategy = 'iron_butterfly'
            else:
                method = self.iron_condor
                strategy = 'iron_condor'
        else:
            strategy = 'credit_spread'
            method = self.credit_spread
        config = strategies[strategy]

        symbol = symbol.upper()
        allocation = self.broker.cash_balance * allocation / 100
        options = self.broker.get_options(symbol)
        timeline_range = config['timeline'][1] - config['timeline'][0]
        timeline = config['timeline'][0] + len(timeline_range) * timeline / 100

        target_date = None
        while target_date not in options['expiration_dates']:
            timeline -= timedelta(days=1)
            target_date = (datetime.now() + timedelta(days=timeline)).strftime("%Y-%m-%d")

        options = self.broker.filter_options(options, [target_date])
        options = self.broker.get_options_data(options)

        legs = method(self, config, symbol, q, options, allocation, target_date, direction)
        self.broker.options_transact(legs, symbol, 'credit')
