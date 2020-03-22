from magictrade.strategy import TradingStrategy
from magictrade.strategy.registry import register_strategy


@register_strategy
class WheelTradingStrategy(TradingStrategy):
    name = 'wheel'

    def make_trade(self, symbol: str, days_out: int = 4, *args, **kwargs):
        symbol = symbol.upper()
        quote = self.broker.get_quote(symbol)
        stock_for_symbol = [s for s in self.broker.stock_positions() if s.symbol.upper() == symbol]
        # Determine the current status and next step; is one of:
        # 1. No positions for {symbol}, sell cash-secured put
        if not stock_for_symbol or stock_for_symbol and not [s for s in stock_for_symbol if s.quantity >= 100]:
            pass
        # 2. We own x>=100*n shares of {symbol} where n>0, sell covered call
        # 3. (2) is true, but also with a covered call open, do nothing?
        pass
