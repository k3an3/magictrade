from statistics import pstdev
from typing import Dict, List

from magictrade.datasource.stock import get_historic_close
from magictrade.strategy import TradingStrategy, TradeException, NoValidLegException
from magictrade.strategy.optionalpha import OptionAlphaTradingStrategy
from magictrade.strategy.registry import register_strategy

# TODO: SPX instead?
INDEX = 'SPY'

config = {
    'timeline': [35, 45],
    'target': 50,
    'direction': 'put',
    'width': 1
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
        ma_20 = historic_closes[-20:] / 20
        ma_3 = historic_closes[-3:] / 3
        u_bb_3_3 = ma_3 / 3 + pstdev(historic_closes[-3:]) * 3
        l_bb_20_1 = ma_20 - pstdev(historic_closes[-20:])
        u_bb_3_1 = ma_3 + pstdev(historic_closes[-3:])
        l_bb_3_3 = ma_3 - pstdev(historic_closes[-3:]) * 3
        u_bb_20_1 = ma_20 + pstdev(historic_closes[-20:])

        # Signals
        signal_1 = u_bb_3_3 < l_bb_20_1
        signal_2 = u_bb_3_1 < ma_20 * 0.99
        signal_3 = l_bb_3_3 > u_bb_20_1

        return signal_1, signal_2, signal_3

    def make_trade(self, symbol: str, allocation: int = 3, *args, **kwargs):
        quote, options, defer = self.init_strategy(symbol)
        if defer:
            return defer
        trade_config = config.copy()

        # Check entry rule
        index_moving_average = get_historic_close(INDEX, 200) / 200
        if not self.broker.get_quote(INDEX) > index_moving_average:
            return {'status': 'deferred'}

        # Calculations
        historic_closes = get_historic_close(symbol, 200)

        signal_1, signal_2, signal_3 = self.check_signals(historic_closes)

        # TODO: determine correct priority if multiple signals fire
        # Note that "probability" is actually delta for TD.
        if signal_1 or signal_2:
            trade_config['max_probability'], trade_config['probability'] = SIGNAL_1_2_DELTA
        elif signal_3:
            trade_config['max_probability'], trade_config['probability'] = SIGNAL_3_DELTA
        else:
            return {'status': 'deferred'}

        legs, target_date = self.find_legs(self.credit_spread, trade_config, options)

        credit, quantity, spread_width = self.prepare_trade(legs, allocation)

        option_order = self.broker.options_transact(legs, 'credit', credit,
                                                    quantity, 'open', strategy='VERTICAL')
        self.save_order(option_order, legs, {}, price=credit, quantity=quantity, symbol=symbol, expires=target_date)
