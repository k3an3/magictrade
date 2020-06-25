from statistics import pstdev
from typing import List

from magictrade.datasource.stock import get_historic_close
from magictrade.strategy.optionalpha import OptionAlphaTradingStrategy
from magictrade.strategy.registry import register_strategy

# TODO: SPX instead?
INDEX = 'SPY'

config = {
    'timeline': [35, 45],
    'target': 50,
    'direction': 'put',
    'width': 1,
    'rr_delta': 1.00
}
SIGNAL_1_2_DELTA = (20, 30.9)
SIGNAL_3_DELTA = (15, 25)


@register_strategy
class BollingerBendStrategy(OptionAlphaTradingStrategy):
    name = 'bollinger_bend'

    def close_position(self, *args, **kwargs):
        return super().close_position(*args, **kwargs, time_in_force='day')

    @staticmethod
    def check_signals(historic_closes: List[float]):
        ma_20 = sum(historic_closes[-20:]) / 20
        ma_3 = sum(historic_closes[-3:]) / 3
        u_bb_3_3 = ma_3 + pstdev(historic_closes[-3:]) * 3
        l_bb_20_1 = ma_20 - pstdev(historic_closes[-20:])
        u_bb_3_1 = ma_3 + pstdev(historic_closes[-3:])
        l_bb_3_3 = ma_3 - pstdev(historic_closes[-3:]) * 3
        u_bb_20_1 = ma_20 + pstdev(historic_closes[-20:])

        # Signals
        signal_1 = u_bb_3_3 < l_bb_20_1
        signal_2 = u_bb_3_1 < ma_20 * 0.99
        signal_3 = l_bb_3_3 > u_bb_20_1

        return signal_1, signal_2, signal_3

    @staticmethod
    def _calc_risk_reward(credit, spread_width) -> float:
        return credit / (spread_width - credit)

    @staticmethod
    def _calc_rr_over_delta(risk_reward: float, delta: float) -> float:
        return risk_reward / delta

    def make_trade(self, symbol: str, allocation: int = 3, dry_run: bool = False, *args, **kwargs):
        quote, options, defer = self.init_strategy(symbol)
        if defer:
            return defer
        trade_config = config.copy()

        # Check entry rule
        # the API considers weekends/holidays as days, so overshoot with the amount of days requested
        index_moving_average = get_historic_close(INDEX, 300)[-200:] / 200
        if not self.broker.get_quote(INDEX) > index_moving_average:
            return {'status': 'deferred', 'msg': 'entry rule fail'}

        # Calculations
        historic_closes = get_historic_close(symbol, 35)

        signal_1, signal_2, signal_3 = self.check_signals(historic_closes)

        # TODO: determine correct priority if multiple signals fire
        # Note that "probability" is actually delta for our TD impl.
        if signal_1 or signal_2:
            trade_config['max_probability'], trade_config['probability'] = SIGNAL_1_2_DELTA
        elif signal_3:
            trade_config['max_probability'], trade_config['probability'] = SIGNAL_3_DELTA
        else:
            return {'status': 'deferred', 'msg': 'no signal'}

        if dry_run:
            # TODO: record in a machine-readable way
            self.log(f"dry run: {symbol} has signals: " + ', '.join(
                [f"signal{n + 1}" for n, s in enumerate((signal_1, signal_2, signal_3)) if s]))
            return {'status': 'skipped', 'msg': 'dry run'}

        legs, target_date = self.find_legs(self.credit_spread, trade_config, options)

        credit, quantity, spread_width = self.prepare_trade(legs, allocation)

        rr = self._calc_risk_reward(credit, spread_width)
        for leg, side in legs:
            if side == 'sell':
                short_leg = leg
        if self._calc_rr_over_delta(rr, short_leg['delta']) < trade_config['rr_delta']:
            return

        option_order = self.broker.options_transact(legs, 'credit', credit,
                                                    quantity, 'open', strategy='VERTICAL')
        self.save_order(option_order, legs, {}, price=credit, quantity=quantity, symbol=symbol, expires=target_date)
