from datetime import timedelta, datetime
from typing import List, Dict, Tuple

from magictrade import Broker, storage
from magictrade.broker import Option
from magictrade.strategy import TradingStrategy, NoValidLegException, TradeException, \
    TradeConfigException, NoTradeException
from magictrade.strategy.registry import register_strategy
from magictrade.utils import get_percentage_change, get_allocation, date_format, get_monthly_option, get_risk

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


@register_strategy
class OptionAlphaTradingStrategy(TradingStrategy):
    name = 'optionalpha'

    def __init__(self, broker: Broker):
        self.broker = broker

    @staticmethod
    def _find_option_with_probability(options: List, probability: int, ttype: str = 'short'):
        for option in sorted(options, key=lambda o: o.probability_otm):
            if option.probability_otm * 100 >= probability:
                return option

    @staticmethod
    def _get_long_leg(options: List, short_leg: Dict, o_type: str, width: int):
        for option in sorted(options, key=lambda o: o.strike_price, reverse=o_type == 'put'):
            if o_type == 'call' and option.strike_price > short_leg.strike_price \
                    or o_type == 'put' and option.strike_price < short_leg.strike_price:
                distance = abs(option.strike_price - short_leg.strike_price)
                if distance >= width:
                    return option
        raise TradeException("No suitable strike price for long leg.")

    def iron_butterfly(self, config: Dict, options: List, **kwargs):
        quote = kwargs['quote']
        calls = self.broker.filter_options(options, option_type='call')
        puts = self.broker.filter_options(options, option_type='put')
        closest_call = min(calls, key=lambda x: abs(x.strike_price - quote))
        for option in puts:
            if option.strike_price == closest_call.strike_price:
                closest_put = option
        call_wing = self._find_option_with_probability(calls, config['probability'])
        put_wing = self._find_option_with_probability(puts, config['probability'])
        return (closest_call, 'sell'), (closest_put, 'sell'), \
               (call_wing, 'buy'), (put_wing, 'buy')

    def iron_condor(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        call_wing = self.credit_spread(config, options, direction='bearish', width=width)
        put_wing = self.credit_spread(config, options, direction='bullish', width=width)
        return call_wing[0], call_wing[1], put_wing[0], put_wing[1]

    def credit_spread(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        direction = kwargs['direction']
        if direction == 'bullish':
            o_type = 'put'
        else:
            o_type = 'call'
        options = self.broker.filter_options(options, option_type=o_type)
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
                                      f"{short_leg.strike_price} and expiration {short_leg.expiration_date}.")

        return (short_leg, 'sell'), (long_leg, 'buy')

    def _get_target_date(self, config: Dict, options: List, timeline: int = 0, days_out: int = 0,
                         blacklist_dates: set = set(), monthly: bool = False):
        if not days_out:
            timeline_range = config['timeline'][1] - config['timeline'][0]
            timeline = config['timeline'][0] + timeline_range * timeline / 100
        else:
            timeline = days_out

        if monthly:
            return get_monthly_option(self.broker.date + timedelta(days=timeline))

        target_date = None
        offset = 0
        if isinstance(options, list):
            dates = self.broker.exp_dates
        else:
            dates = options['expiration_dates']
        while not target_date:
            td1 = date_format(self.broker.date + timedelta(days=timeline + offset))
            td2 = date_format(self.broker.date + timedelta(days=timeline - offset))
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
                leg_price = leg[0].mark_price
            else:
                action = leg['side']
                leg_price = leg.mark_price
            if action == 'sell':
                price += leg_price
            elif action == 'buy':
                price -= leg_price
        return price

    @staticmethod
    def _get_quantity(allocation: float, spread_width: float, price: float = 0.0) -> int:
        return int(allocation / get_risk(spread_width, price))

    @staticmethod
    def _calc_spread_width(legs: List[Tuple[Option, str]]):
        leg_map = {}
        map_format = "{}:{}"
        for leg, side in legs:
            leg_map[map_format.format(side, leg.option_type)] = leg.strike_price
        widths = []
        for t in ('call', 'put'):
            try:
                widths.append(abs(leg_map[map_format.format('sell', t)] - leg_map[map_format.format('buy', t)]))
            except KeyError:
                pass
        return max(widths)

    def log(self, msg: str) -> None:
        storage.lpush(self.get_name() + ":log", "{} {}".format(datetime.now().timestamp(), msg))

    @staticmethod
    def _get_fair_credit(legs: List[Tuple[Option, str]], spread_width: float) -> float:
        probability_itm = 0
        for option, side in legs:
            if side == 'sell':
                probability_itm += option.probability_itm
        return spread_width * probability_itm

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
            if value <= 0:
                self.log(f"Calculated negative credit ({value:.2f}) during maintenance "
                         f"on {data['symbol']}-{data['strategy']}, skipping...")
                continue
            change = get_percentage_change(float(data['price']), value)
            data['last_price'] = value
            data['last_change'] = change * -1
            storage.hmset("{}:{}".format(self.get_name(), position), data)
            if value and -1 * change >= strategies[data['strategy']]['target']:
                # legs that were originally bought now need to be sold
                self.invert_action(legs)
                self.log("[{}]: Closing {}-{} due to change of {:.2f}%."
                         " Was {:.2f}, now {:.2f}.".format(position,
                                                           data['symbol'],
                                                           data['strategy'],
                                                           change,
                                                           float(data['price']),
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
                   spread_width: int = 3, days_out: int = 0, monthly: bool = False, exp_date: str = None,
                   open_criteria: List = [], close_criteria: List = []):
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

        if open_criteria and not self.evaluate_criteria(open_criteria,
                                                        date=self.broker.date.timestamp(),
                                                        price=quote):
            return {'status': 'deferred'}

        options = self.broker.get_options(symbol)
        if not options:
            raise NoTradeException(f"No options found for {symbol}.")

        blacklist_dates = set()

        attempts = 0
        while attempts <= 7:
            # Only try the specified date once.
            if exp_date:
                target_date = exp_date
                attempts = 7
            else:
                target_date = self._get_target_date(config, options, timeline, days_out, blacklist_dates,
                                                    monthly=monthly)
                # Only try one monthly option
                if monthly:
                    attempts = 7
            blacklist_dates.add(target_date)
            attempts += 1

            if not (options_on_date := self.broker.filter_options(options, [target_date])):
                continue
            options_on_date = self.broker.get_options_data(options_on_date)

            try:
                legs = method(config, options_on_date, quote=quote, direction=direction, width=spread_width)
                break
            except NoValidLegException:
                continue
        else:
            raise TradeException("Could not find a valid expiration date with suitable strikes, "
                                 "or supplied expiration date has no options.")
        # Calculate net credit
        credit = self._get_price(legs)
        if credit <= 0:
            raise TradeException(f"Calculated negative credit ({credit:.2f}), bailing.")
        allocation = get_allocation(self.broker, allocation)
        # Get actual spread width--the stock may only offer options at a larger interval than specified.
        spread_width = self._calc_spread_width(legs)
        if not credit >= (min_credit := self._get_fair_credit(legs, spread_width)):
            # TODO: decide what to do
            self.log(
                f"Trade isn't fair; received credit {credit:.2f} < {min_credit:.2f}. Placing anyway.")
        # Calculate what quantity is appropriate for the given allocation and risk.
        quantity = self._get_quantity(allocation, spread_width, credit)
        if not quantity:
            raise NoTradeException("Trade quantity equals 0. Ensure allocation is high enough, or enough capital is "
                                   "available.")
        option_order = self.broker.options_transact(legs, 'credit', credit,
                                                    quantity, 'open', strategy=strategy)
        self.save_order(option_order, legs, {}, strategy=strategy, price=credit,
                        quantity=quantity, expires=target_date, symbol=symbol,
                        close_criteria=close_criteria)
        self.log("[{}]: Opened {} in {} with direction {} with quantity {} and price {}.".format(
            option_order.id,
            strategy,
            symbol,
            direction,
            quantity,
            round(credit * 100, 2)))
        return {'status': 'placed', 'strategy': strategy, 'legs': legs, 'quantity': quantity,
                'price': quantity * credit, 'order': option_order}
