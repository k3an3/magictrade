from typing import List, Dict

from magictrade.strategy import TradingStrategy, TradeException, NoTradeException, NoValidLegException
from magictrade.strategy.registry import register_strategy
from magictrade.utils import find_option_with_probability, get_allocation

config = {
    'timeline': [30, 45],
    'target': 100,
    'probability': 70,
}


@register_strategy
class WheelTradingStrategy(TradingStrategy):
    name = 'wheel'

    @staticmethod
    def _100_shares_owned(stock_positions: List):
        return [s for s in stock_positions if s.quantity >= 100]

    def get_option(self, config: Dict, options: List, option_type: str):
        options = self.broker.filter_options(options, option_type=option_type)
        option = find_option_with_probability(options, config['probability'])
        if not option:
            raise NoValidLegException("Failed to find a suitable option for the trade with probability in range.")
        return option

    def make_trade(self, symbol: str, days_out: int = 4, allocation: int = 5, open_criteria: List = [],
                   close_criteria: List = [], *args, **kwargs):
        # TODO: recurring
        quote, options, defer = self.init_strategy(symbol, open_criteria)
        if defer:
            return defer

        stock_for_symbol = [s for s in self.broker.stock_positions() if s.symbol.upper() == symbol.upper()]
        # Determine the current status and next step; is one of:
        # 1. No positions for {symbol}, sell cash-secured put
        if not stock_for_symbol or stock_for_symbol and not self._100_shares_owned(stock_for_symbol):
            option_type = 'put'
        # 2. We own x>=100*n shares of {symbol} where n>0, sell covered call
        elif self._100_shares_owned(stock_for_symbol):
            option_type = 'call'
        # 3. (2) is true, but also with a covered call open, do nothing?
        else:
            raise NoTradeException("Nothing to do.")

        for target_date, options_on_date in self.find_exp_date(config, options, 0, days_out, False, None):
            try:
                option = self.get_option(config, options_on_date, option_type)
                break
            except NoValidLegException:
                continue
        else:
            raise TradeException("Could not find a valid expiration date with a suitable strike, "
                                 "or supplied expiration date has no options.")
        credit = option.mark_price
        quantity = 1
        if credit <= 0:
            raise TradeException(f"Calculated negative credit ({credit:.2f}), bailing.")
        allocation = get_allocation(self.broker, allocation)
        if not self.broker.buying_power >= option.strike_price * 100:
            raise NoTradeException("Can't afford to be assigned")
        elif not allocation >= option.strike_price * 100:
            raise NoTradeException("Trade quantity equals 0. Ensure allocation is high enough, or enough capital is "
                                   "available.")
        option_order = self.broker.options_transact([option], 'credit', credit,
                                                    quantity, 'open')
        self.save_order(option_order, [option], {}, strategy='wheel', price=credit,
                        quantity=quantity, expires=target_date, symbol=symbol,
                        close_criteria=close_criteria)
        self.log("[{}]: Opened {} in {} for wheel. Received credit {}.".format(
            option_order.id,
            option.option_type,
            symbol,
            round(credit * 100, 2)))
        return {'status': 'placed', 'strategy': 'wheel', 'legs': [option], 'quantity': quantity,
                'price': quantity * credit, 'order': option_order}

    def _maintenance(self):
        return []

    def close_position(self, position: str, data: Dict, legs: List):
        raise NotImplementedError()
