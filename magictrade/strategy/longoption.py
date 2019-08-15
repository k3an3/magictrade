import re
from typing import List, Dict

from magictrade import Broker
from magictrade.strategy import TradingStrategy, TradeException, TradeConfigException
from magictrade.utils import get_allocation

strategies = {
}

total_allocation = 40
option_types = ('call', 'put')


class LongOptionTradingStrategy(TradingStrategy):
    name = 'longoption'

    def __init__(self, broker: Broker):
        self.broker = broker

    def maintenance(self) -> List:
        pass

    @staticmethod
    def find_option(options: List, strike_price: float) -> Dict:
        return next([option for option in options if float(option['strike_price']) == strike_price ])

    def make_trade(self, symbol: str, option_type: str, strike_price: float, expiration_date: str, allocation_percent: int = 0,
                   allocation_dollars: int = 0):
        if option_type not in option_types:
            raise TradeConfigException("Option type must be one of 'call' or 'put'.")

        if not allocation_dollars >= 0:
            raise TradeConfigException("Allocation dollar amount must be positive.")

        if not allocation_percent >= 0:
            raise TradeConfigException("Allocation percent must be positive.")

        if not re.search(r'^(20[0-9]{2})-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])$', expiration_date):
            raise TradeConfigException("Expiration date format must be YYYY-MM-DD.")

        if not strike_price > 0:
            raise TradeConfigException("Invalid strike price.")

        symbol = symbol.upper()
        quote = self.broker.get_quote(symbol)
        if not quote:
            raise TradeException("Error getting quote for " + symbol)

        options = self.broker.get_options(quote)
        options = self.broker.filter_options(options, [expiration_date])
        if not options:
            raise TradeException(f"No options for {symbol} found with the provided expiration date '{expiration_date}'.")
        # Get data, but not all options will return data. Filter them out.
        options = [o for o in self.broker.get_options_data(options) if o.get('mark_price')]

        try:
            option = self.find_option(options, strike_price)
        except StopIteration:
            raise TradeException(f"Could not find option with strike price {strike_price}")

        allocation = get_allocation(self.broker, allocation_percent) if allocation_percent else allocation_dollars
        price = option['mark_price']
        quantity = int(allocation / price)
        if not quantity:
            raise TradeException("Trade quantity equals 0.")

        option_order = self.broker.options_transact([option], 'debit', price, quantity, 'open')
        self.save_order(option_order, [option], price=price, quantity=quantity, expires=expiration_date)

        self.log("[{}]: Bought {} in {} with quantity {} and price {}.".format(
            option_order["id"],
            option_type,
            symbol,
            quantity,
            round(price * 100, 2)))
        return {'status': placed}