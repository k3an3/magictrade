from datetime import timedelta
from typing import List, Dict

from magictrade import Broker, storage
from magictrade.strategy import TradingStrategy, NoValidLegException, TradeException, filter_option_type, \
    TradeConfigException
from magictrade.utils import get_percentage_change, get_allocation

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


class OptionAlphaTradingStrategy(TradingStrategy):
    name = 'oatrading'

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
    def _get_long_leg(options: List, short_leg: Dict, o_type: str, width: int):
        for option in sorted(options, key=lambda o: o['strike_price'], reverse=o_type == 'put'):
            if o_type == 'call' and option['strike_price'] > short_leg['strike_price'] \
                    or o_type == 'put' and option['strike_price'] < short_leg['strike_price']:
                distance = abs(option['strike_price'] - short_leg['strike_price'])
                if distance >= width:
                    return option
        raise TradeException("No suitable strike price for long leg.")

    def iron_butterfly(self, config: Dict, options: List, **kwargs):
        quote = kwargs['quote']
        calls = filter_option_type(options, 'call')
        puts = filter_option_type(options, 'put')
        closest_call = min(calls, key=lambda x: abs(x['strike_price'] - quote))
        for option in puts:
            if option['strike_price'] == closest_call['strike_price']:
                closest_put = option
        call_wing = self._find_option_with_probability(calls, config['probability'])
        put_wing = self._find_option_with_probability(puts, config['probability'])
        return (closest_call, 'sell'), (closest_put, 'sell'), \
               (call_wing, 'buy'), (put_wing, 'buy')

    def iron_condor(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        call_wing = self.credit_spread(config, filter_option_type(options, 'call'), direction='bearish',
                                       width=width)
        put_wing = self.credit_spread(config, filter_option_type(options, 'put'), direction='bullish',
                                      width=width)
        return call_wing[0], call_wing[1], put_wing[0], put_wing[1]

    def credit_spread(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        direction = kwargs['direction']
        if direction == 'bullish':
            o_type = 'put'
        else:
            o_type = 'call'
        options = filter_option_type(options, o_type)
        if not options:
            raise TradeException("No options found.")
        short_leg = self._find_option_with_probability(options, config['probability'])
        if not short_leg:
            raise NoValidLegException("Failed to find a suitable short leg for the trade with probability in range.")
        long_leg = None
        while not long_leg and width > 0:
            try:
                long_leg = self._get_long_leg(options, short_leg, o_type, width)
            except TradeException:
                width -= 1
        if not long_leg:
            raise NoValidLegException(f"Failed to find a suitable long leg for the trade. Short leg strike at "
                                      f"{short_leg['strike_price']} and expiration {short_leg['expiration_date']}.")

        return (short_leg, 'sell'), (long_leg, 'buy')

    def _get_target_date(self, config: Dict, options: List, timeline: int = 0, days_out: int = 0,
                         blacklist_dates: set = set()):
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
            if td1 in dates and td1 not in blacklist_dates:
                target_date = td1
            elif td2 in dates and td2 not in blacklist_dates:
                target_date = td2
            offset += 1
        return target_date

    @staticmethod
    def _get_price(legs: List) -> float:
        price = 0
        for leg in legs:
            if len(leg) == 2:
                action = leg[1]
                leg_price = leg[0]['mark_price']
            else:
                action = leg['side']
                leg_price = leg['mark_price']
            if action == 'sell':
                price += leg_price
            elif action == 'buy':
                price -= leg_price
        return price

    @staticmethod
    def _get_quantity(allocation: float, spread_width: float) -> int:
        return int(allocation / (spread_width * 100))

    @staticmethod
    def invert_action(legs: List) -> None:
        for leg in legs:
            if leg['side'] == 'buy':
                leg['side'] = 'sell'
            else:
                leg['side'] = 'buy'

    def maintenance(self) -> List:
        orders = []

        for position, data, legs in self.get_current_positions():
            legs = self.broker.options_positions_data(legs)
            value = self._get_price(legs)
            change = get_percentage_change(float(data['price']), value)
            data['last_price'] = value
            data['last_change'] = change * -1
            storage.hmset("{}:{}".format(self.get_name(), position), data)
            if value and -1 * change >= strategies[data['strategy']]['target']:
                self.invert_action(legs)
                self.log("[{}]: Closing {}-{} due to change of {:.2f}%. Was {:.2f}, now {:.2f}.".format(position,
                                                                                                        data['symbol'],
                                                                                                        data[
                                                                                                            'strategy'],
                                                                                                        change,
                                                                                                        float(data[
                                                                                                                  'price']),
                                                                                                        value))
                option_order = self.broker.options_transact(legs, 'debit', value,
                                                            int(data['quantity']),
                                                            'close', time_in_force="gtc",
                                                            )
                self.delete_position(position)
                orders.append(option_order)
                self.log("[{}]: Closed {}-{} with quantity {} and price {:.2f}.".format(position,
                                                                                        data['symbol'],
                                                                                        data['strategy'],
                                                                                        data['quantity'],
                                                                                        value))
        return orders

    def make_trade(self, symbol: str, direction: str, iv_rank: int = 50, allocation: int = 3, timeline: int = 50,
                   spread_width: int = 3, days_out: int = 0):
        if direction not in valid_directions:
            raise TradeConfigException("Invalid direction. Must be in " + str(valid_directions))

        if not 0 <= iv_rank <= 100:
            raise TradeConfigException("Invalid iv_rank.")

        if not 0 < allocation < 20:
            raise TradeConfigException("Invalid allocation amount or crazy.")

        if not iv_rank >= 50:
            raise TradeConfigException("iv_rank too low.")
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
        quote = self.broker.get_quote(symbol)
        if not quote:
            raise TradeException("Error getting quote for " + symbol)

        options = self.broker.get_options(symbol)

        blacklist_dates = set()

        attempts = 0
        while attempts <= 7:
            target_date = self._get_target_date(config, options, timeline, days_out, blacklist_dates)
            blacklist_dates.add(target_date)
            attempts += 1

            if not (options_on_date := self.broker.filter_options(options, [target_date])):
                continue
            # Get data, but not all options will return data. Filter them out.
            options_on_date = [o for o in self.broker.get_options_data(options_on_date) if o.get('mark_price')]

            try:
                legs = method(config, options_on_date, quote=quote, direction=direction, width=spread_width)
                break
            except NoValidLegException:
                continue
        else:
            raise TradeException("Could not find a valid expiration date with suitable strikes.")

        price = self._get_price(legs)
        allocation = get_allocation(self.broker, allocation)
        quantity = self._get_quantity(allocation, spread_width)
        if not quantity:
            raise TradeException("Trade quantity equals 0.")
        option_order = self.broker.options_transact(legs, 'credit', price,
                                                    quantity, 'open')
        self.save_order(option_order, legs, {}, strategy=strategy, price=price,
                        quantity=quantity, expires=target_date, symbol=symbol)
        self.log("[{}]: Opened {} in {} for direction {} with quantity {} and price {}.".format(
            option_order["id"],
            strategy,
            symbol,
            direction,
            quantity,
            round(price * 100, 2)))
        return {'status': 'placed', 'strategy': strategy, 'legs': legs, 'quantity': quantity,
                'price': quantity * price, 'order': option_order}
