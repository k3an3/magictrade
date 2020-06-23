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


@register_strategy
class BollingerBendStrategy(OptionAlphaTradingStrategy):
    name = 'bollinger_bend'

    def _maintenance(self, position: str, data: Dict, legs: List) -> List:
        pass

    def close_position(self, position: str, data: Dict, legs: List):
        pass

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
            trade_config['probability'] = 30.9
        elif signal_3:
            trade_config['probability'] = 25
        else:
            return {'status': 'deferred'}

        # Find suitable legs
        for target_date, options_on_date in self.find_exp_date(config, options):
            try:
                legs = self.credit_spread(trade_config, options_on_date)
                break
            except NoValidLegException:
                continue
        else:
            raise TradeException("Could not find a valid expiration date with suitable strikes, "
                                 "or supplied expiration date has no options.")

        # Calculate
        credit, quantity, spread_width = self.prepare_trade(legs, allocation)

        option_order = self.broker.options_transact(legs, 'credit', credit,
                                                    quantity, 'open', strategy='VERTICAL')
