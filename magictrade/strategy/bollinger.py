import datetime
from statistics import pstdev
from typing import List

from magictrade.strategy.optionseller import OptionSellerTradingStrategy
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
SIGNAL_1_2_DELTA = (100 - 20, 100 - 30.9)
SIGNAL_3_DELTA = (100 - 15, 100 - 25)


@register_strategy
class BollingerBendStrategy(OptionSellerTradingStrategy):
    name = 'bollinger_bend'

    def _maintenance(self, *args, **kwargs):
        # Trades should only be placed in the last hour.
        if datetime.datetime.now().hour < 15:
            return
        return super()._maintenance(*args, **kwargs)

    def close_position(self, *args, **kwargs):
        return super().close_position(*args,
                                      **kwargs,
                                      delete=False,
                                      time_in_force='day')

    @staticmethod
    def check_signals(historic_closes: List[float]):
        ma_20 = sum(historic_closes[-20:]) / 20
        prev_ma_20 = sum(historic_closes[-21:-1]) / 20
        ma_3 = sum(historic_closes[-3:]) / 3
        u_bb_3_3 = ma_3 + pstdev(historic_closes[-3:]) * 3
        l_bb_20_1 = ma_20 - pstdev(historic_closes[-20:])
        u_bb_3_1 = ma_3 + pstdev(historic_closes[-3:])
        prev_u_bb_3_1 = sum(historic_closes[-4:-1]) / 3 + pstdev(
            historic_closes[-4:-1])
        l_bb_3_3 = ma_3 - pstdev(historic_closes[-3:]) * 3
        u_bb_20_1 = ma_20 + pstdev(historic_closes[-20:])

        # Signals
        signal_1 = u_bb_3_3 < l_bb_20_1
        signal_2 = u_bb_3_1 < ma_20 * 0.99 and prev_u_bb_3_1 > prev_ma_20 * 0.99
        signal_3 = l_bb_3_3 > u_bb_20_1

        return signal_1, signal_2, signal_3

    @staticmethod
    def _calc_risk_reward(credit, spread_width) -> float:
        return credit / (spread_width - credit)

    @staticmethod
    def _calc_rr_over_delta(risk_reward: float, delta: float) -> float:
        return risk_reward / delta

    def make_trade(self,
                   symbol: str,
                   allocation: int = 3,
                   signal_1: bool = False,
                   signal_2: bool = False,
                   signal_3: bool = False,
                   dry_run: bool = False,
                   *args,
                   **kwargs):
        trade_config = config.copy()

        # Note that "probability" is actually delta for our TD impl.
        if signal_1 or signal_2:
            trade_config['max_probability'], trade_config[
                'probability'] = SIGNAL_1_2_DELTA
        elif signal_3:
            trade_config['max_probability'], trade_config[
                'probability'] = SIGNAL_3_DELTA
        else:
            return {'status': 'deferred', 'msg': 'no signal'}

        quote, options, defer = self.init_strategy(symbol)
        if defer:
            return defer

        legs, target_date = self.find_legs(self.credit_spread,
                                           trade_config,
                                           options,
                                           max_spread_width=5)

        credit, quantity, spread_width = self.prepare_trade(legs, allocation)

        rr = self._calc_risk_reward(credit, spread_width)
        for leg, side in legs:
            if side == 'sell':
                short_leg = leg
        if rr_delta := self._calc_rr_over_delta(
                rr, short_leg['delta']) < trade_config['rr_delta']:
            return {
                'status': 'rejected',
                'msg':
                f'risk reward/delta ratio too low: {rr_delta}/{trade_config["rr_delta"]}'
            }

        option_order = self.broker.options_transact(legs,
                                                    'credit',
                                                    credit,
                                                    quantity,
                                                    'open',
                                                    strategy='VERTICAL')
        self.save_order(option_order,
                        legs, {},
                        price=credit,
                        quantity=quantity,
                        symbol=symbol,
                        expires=target_date)
