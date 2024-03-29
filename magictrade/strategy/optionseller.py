from typing import List, Dict, Tuple

from magictrade.securities import Option
from magictrade.strategy import TradingStrategy, NoValidLegException, TradeException, \
    TradeConfigException
from magictrade.strategy.registry import register_strategy
from magictrade.utils import find_option_with_probability, get_price_from_change

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
valid_directions = {'neutral', 'bullish', 'bearish', 'put', 'call'}


@register_strategy
class OptionSellerTradingStrategy(TradingStrategy):
    name = 'optionseller'

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
        call_wing = find_option_with_probability(calls, config['probability'])
        put_wing = find_option_with_probability(puts, config['probability'])
        return (closest_call, 'sell'), (closest_put, 'sell'), \
               (call_wing, 'buy'), (put_wing, 'buy')

    def iron_condor(self, config: Dict, options: List, **kwargs):
        width = kwargs['width']
        call_wing = self.credit_spread(config, options, direction='bearish', width=width)
        put_wing = self.credit_spread(config, options, direction='bullish', width=width)
        return call_wing[0], call_wing[1], put_wing[0], put_wing[1]

    def find_leg(self, options: List[Option], criteria: str, sort_key: str = 'probability_otm',
                 reverse: bool = False, absolute_key: bool = False) -> Option:
        # TODO hack
        if sort_key == 'delta':
            absolute_key = True
        # TODO gross
        if absolute_key:
            def sort_key_func(o: Option) -> float:
                try:
                    return abs(getattr(o, sort_key))
                except TypeError:
                    return -1.0
        else:
            def sort_key_func(o: Option) -> float:
                return getattr(o, sort_key)

        # TODO: reverse not working
        for option in sorted(options, key=sort_key_func)[::-1 if reverse else 1]:
            try:
                if self.evaluate_criteria([criteria], **option):
                    return option
            except TypeError:
                continue

    def credit_spread(self, config: Dict, options: List, leg_criteria: Dict = {}, **kwargs):
        width = kwargs.get('width', config.get('width'))
        direction = kwargs.get('direction', config.get('direction'))
        if direction in {'bullish', 'put'}:
            o_type = 'put'
        elif direction in {'bearish', 'call'}:
            o_type = 'call'
        else:
            raise TradeException("No direction supplied.")
        options = self.broker.filter_options(options, option_type=o_type)
        if not options:
            raise TradeException("No options found.")
        if leg_criteria:
            short_leg = self.find_leg(options, leg_criteria, kwargs.get('sort_key'),
                                      reverse=kwargs.get('sort_reverse'))
        else:
            short_leg = find_option_with_probability(options, config['probability'],
                                                     max_probability=config.get('max_probability', 100))
        if not short_leg:
            raise NoValidLegException("Failed to find a suitable short leg for the trade with probability in range.")
        long_leg = None
        while not long_leg and width > 0:
            try:
                long_leg = self._get_long_leg(options, short_leg, o_type, width)
            except TradeException:
                if width < kwargs.get("max_spread_width", 0):
                    width += 1
                else:
                    width -= 1
        if not long_leg:
            raise NoValidLegException(f"Failed to find a suitable long leg for the trade. Short leg strike at "
                                      f"{short_leg.strike_price} and expiration {short_leg.expiration_date}.")

        return (short_leg, 'sell'), (long_leg, 'buy')

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

    def close_position(self, position: str, data: Dict, legs: List, close_price: float = 0.0, delete: bool = False,
                       time_in_force: str = "day"):
        if not close_price:
            close_price = self._get_price(legs)
        self.invert_action(legs)
        option_order = self.broker.options_transact(legs, 'debit', close_price,
                                                    1,
                                                    'close', time_in_force=time_in_force,
                                                    )
        if delete:
            self.delete_position(position)
        return option_order

    def _maintenance(self, position: str, data: Dict, legs: List, value: float, change: float, config: Dict = {}) -> List:
        legs = self.broker.options_positions_data(legs)
        strategy = config.get('strategy', data.get('strategy', 'unknown'))
        if not config:
            config = strategies[strategy]
        if value <= 0:
            self.log(f"Calculated negative credit ({value:.2f}) during maintenance "
                     f"on {data['symbol']}-{strategy}, skipping...")
            return
        if value and -1 * change >= config['target']:
            # legs that were originally bought now need to be sold
            self.log("[{}]: Closing {}-{} due to change of {:.2f}%."
                     " Was {:.2f}, now {:.2f}.".format(position,
                                                       data['symbol'],
                                                       strategy,
                                                       abs(change),
                                                       float(data['price']),
                                                       value))
            option_order = self.close_position(position, data, legs, value)
            self.log("[{}]: Closed {}-{} with quantity {} and price {:.2f}.".format(position,
                                                                                    data['symbol'],
                                                                                    strategy,
                                                                                    data['quantity'],
                                                                                    value))
            return option_order

    def make_trade(self, symbol: str, direction: str = "", iv_rank: int = 50, allocation: int = 3, timeline: int = 50,
                   spread_width: int = 3, days_out: int = 0, monthly: bool = False, exp_date: str = None,
                   open_criteria: List = [], close_criteria: List = [], immediate_closing_order: bool = False,
                   leg_criteria: str = '', account_name: str = '', trade_criteria: Dict = {}, sort_by: str = "",
                   sort_reverse: bool = False):
        if direction and direction not in valid_directions:
            raise TradeConfigException("Invalid direction. Must be in " + str(valid_directions))

        if iv_rank and not 0 <= iv_rank <= 100:
            raise TradeConfigException("Invalid IV rank.")

        if not 0 < allocation < 20:
            raise TradeConfigException("Invalid allocation amount or too high.")

        if iv_rank and not iv_rank >= 50:
            raise TradeConfigException("IV rank too low.")
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

        quote, options, defer = self.init_strategy(symbol, open_criteria)
        if defer:
            return defer

        legs, target_date = self.find_legs(method, config, options, timeline, days_out, monthly, exp_date,
                                           quote=quote, direction=direction, width=spread_width,
                                           leg_criteria=leg_criteria, sort_key=sort_by, sort_reverse=sort_reverse)

        credit, quantity, spread_width = self.prepare_trade(legs, allocation)

        if "rr_delta" in trade_criteria:
            rr = self._calc_risk_reward(credit, spread_width)
            for leg, side in legs:
                if side == 'sell':
                    short_leg = leg
            if (rr_delta := self._calc_rr_over_delta(
                    rr, short_leg['delta'])) < trade_criteria["rr_delta"]:
                return {
                    'status': 'rejected',
                    'msg': f'risk reward/delta ratio too low: {round(rr_delta, 2)}/{round(trade_criteria["rr_delta"], 2)}'
                }
        elif not credit >= (min_credit := self._get_fair_credit(legs, spread_width)):
            # TODO: decide what to do
            self.log(
                f"Trade isn't fair; received credit {credit:.2f} < {min_credit:.2f}. Placing anyway.")

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
        if immediate_closing_order:
            # TODO: Actually, this doesn't make sense since we haven't guaranteed to fill yet. Find a way to defer this.
            close_price = get_price_from_change(credit, config['target'])
            self.close_position(None, {'quantity': quantity}, legs, close_price, delete=False)
            self.log(f"[{option_order.id}] Placing closing order with debit {round(close_price, 2)}.")
        return {'status': 'placed', 'strategy': strategy, 'legs': legs, 'quantity': quantity,
                'price': quantity * credit, 'order': option_order}
