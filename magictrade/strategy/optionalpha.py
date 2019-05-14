import json
from datetime import timedelta, datetime
from typing import List, Dict

from magictrade import Broker, storage
from magictrade.strategy import TradingStrategy
from magictrade.utils import get_percentage_change

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
        'probability': 70,
    },
}

high_iv = 75
total_allocation = 40
valid_directions = ('neutral', 'bullish', 'bearish')


class TradeException(Exception):
    pass


class OptionAlphaTradingStrategy(TradingStrategy):
    name = 'oatrading'

    def __init__(self, broker: Broker):
        self.broker = broker

    def get_name(self):
        return "{}-{}".format(self.name, self.broker.account_id)

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
    def _get_long_leg(options: List, short_leg: Dict, o_type: str, width: int):
        for option in sorted(options, key=lambda o: o['strike_price'], reverse=o_type == 'put'):
            if o_type == 'call' and option['strike_price'] > short_leg['strike_price'] \
                    or o_type == 'put' and option['strike_price'] < short_leg['strike_price']:
                distance = abs(option['strike_price'] - short_leg['strike_price'])
                if distance >= width:
                    return option

    def iron_butterfly(self, config: Dict, options: List, **kwargs):
        quote = kwargs['quote']
        calls = self._filter_option_type(options, 'call')
        puts = self._filter_option_type(options, 'put')
        closest_call = min(calls, key=lambda x: abs(x['strike_price'] - quote))
        for option in puts:
            if option['strike_price'] == closest_call['strike_price']:
                closest_put = option
        call_wing = self._find_option_with_probability(calls, config['probability'])
        put_wing = self._find_option_with_probability(puts, config['probability'])
        return (closest_call, 'sell', 'open'), (closest_put, 'sell', 'open'), \
               (call_wing, 'buy', 'open'), (put_wing, 'buy', 'open')

    def iron_condor(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        call_wing = self.credit_spread(config, self._filter_option_type(options, 'call'), direction='bearish',
                                       width=width)
        put_wing = self.credit_spread(config, self._filter_option_type(options, 'put'), direction='bullish',
                                      width=width)
        return call_wing[0], call_wing[1], put_wing[0], put_wing[1]

    def credit_spread(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        direction = kwargs['direction']
        if direction == 'bullish':
            o_type = 'put'
        else:
            o_type = 'call'
        options = self._filter_option_type(options, o_type)
        short_leg = self._find_option_with_probability(options, config['probability'])
        long_leg = self._get_long_leg(options, short_leg, o_type, width)
        return (short_leg, 'sell', 'open'), (long_leg, 'buy', 'open')

    def _get_allocation(self, allocation: int):
        return self.broker.balance * allocation / 100

    def _get_target_date(self, config: Dict, options: List, timeline: int = 0, days_out: int = 0):
        if not days_out:
            timeline_range = config['timeline'][1] - config['timeline'][0]
            timeline = config['timeline'][0] + timeline_range * timeline / 100
        else:
            timeline = days_out

        target_date = None
        offset = 0
        if isinstance(options, list):
            dates = self.broker.exp_dates
        else:
            dates = options['expiration_dates']
        while not target_date:
            td1 = (self.broker.date + timedelta(days=timeline + offset)).strftime("%Y-%m-%d")
            td2 = (self.broker.date + timedelta(days=timeline - offset)).strftime("%Y-%m-%d")
            if td1 in dates:
                target_date = td1
            elif td2 in dates:
                target_date = td2
            offset += 1
        return target_date

    @staticmethod
    def _get_price(legs: List):
        price = 0
        for leg in legs:
            if len(leg) == 3:
                action = leg[1]
                leg_price = leg[0]['mark_price']
            else:
                action = leg['side']
                leg_price = leg['mark_price']
            if action == 'sell':
                price += leg_price
            elif action == 'buy':
                price -= leg_price
        return price * 100

    @staticmethod
    def _get_quantity(allocation: float, spread_width: float):
        return int(allocation / (spread_width * 100))

    def log(self, msg: str):
        storage.lpush(self.get_name() + ":log", msg)

    def _delete_position(self, order_id: str):
        storage.lrem("{}:positions".format(self.get_name()), 0, order_id)
        for leg in storage.lrange("{}:{}:legs".format(self.get_name(), order_id), 0, -1):
            storage.delete("{}:leg:{}".format(self.get_name(), leg))
        storage.delete("{}:{}:legs".format(self.get_name(), order_id))
        storage.delete("{}:{}".format(self.get_name(), order_id))

    def maintenance(self):
        positions = storage.lrange(self.get_name() + ":positions", 0, -1)
        orders = []
        for position in positions:
            data = storage.hgetall("{}:{}".format(self.get_name(), position))
            leg_ids = storage.lrange("{}:{}:legs".format(self.get_name(), position), 0, -1)
            legs = []
            for leg in leg_ids:
                legs.append(storage.hgetall("{}:leg:{}".format(self.get_name(), leg)))
            legs = self.broker.options_positions_data(legs)
            value = self._get_price(legs)
            change = get_percentage_change(float(data['price']), value)
            if -1 * change >= strategies[data['strategy']]['target']:
                option_order = self.broker.options_transact(legs, data['symbol'],
                                                            'debit', value,
                                                            data['quantity'],
                                                            'close'
                                                            )
                self._delete_position(position)
                orders.append(option_order)
                self.log("Closed {} with quantity {} and price {}.".format(data['strategy'],
                                                                           data['quantity'],
                                                                           value))
        return orders

    def make_trade(self, symbol: str, direction: str, iv_rank: int = 50, allocation: int = 3, timeline: int = 50,
                   spread_width: int = 3, days_out: int = 0):
        # TODO Decide if a trade should even be made based on cash reserves. Probably in whatever calls this
        q = self.broker.get_quote(symbol)

        if direction not in valid_directions:
            raise TradeException("Invalid direction. Must be in " + str(valid_directions))

        if not 0 <= iv_rank <= 100:
            raise TradeException("Invalid iv_rank.")

        if not 0 < allocation < 20:
            raise TradeException("Invalid allocation amount or crazy.")

        if not iv_rank >= 50:
            raise TradeException("iv_rank too low.")
        elif direction == 'neutral':
            if iv_rank >= high_iv:
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
        allocation = self._get_allocation(allocation)
        options = self.broker.get_options(symbol)

        target_date = self._get_target_date(config, options, timeline)

        options = self.broker.filter_options(options, [target_date])
        options = self.broker.get_options_data(options)

        legs = method(config, options, quote=q, direction=direction, width=spread_width)

        price = self._get_price(legs)
        quantity = self._get_quantity(allocation, spread_width)
        option_order = self.broker.options_transact(legs, symbol, 'credit', price,
                                                    quantity, 'open')
        storage.lpush(self.get_name() + ":positions", option_order["id"])
        storage.hmset("{}:{}".format(self.get_name(), option_order["id"]),
                      {
                          'strategy': strategy,
                          'price': price,
                          'quantity': quantity,
                          'symbol': symbol,
                      })
        for leg in option_order["legs"]:
            storage.lpush("{}:{}:legs".format(self.get_name(), option_order["id"]),
                          leg["id"])
            storage.hmset("{}:leg:{}".format(self.get_name(), leg["id"]), leg)
        storage.lpush("{}:raw:{}".format(self.get_name(), option_order["id"]), str(legs))
        self.log("{} [{}]: Opened {} in {} for direction {} with quantity {} and price {}.".format(
            datetime.now().timestamp(),
            option_order["id"],
            strategy,
            symbol,
            direction,
            quantity,
            round(price, 2)))
        return strategy, legs, quantity, quantity * price, option_order