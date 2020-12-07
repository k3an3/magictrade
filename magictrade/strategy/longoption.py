import re
from typing import List, Dict

from magictrade.strategy import TradingStrategy, TradeException, TradeConfigException, filter_option_type, \
    TradeDateException
from magictrade.strategy.registry import register_strategy
from magictrade.utils import get_allocation, get_offset_date

strategies = {
}

total_allocation = 40
option_types = ('call', 'put')
DATE_REGEX = re.compile(r'^(20[0-9]{2})-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])$')


@register_strategy
class LongOptionTradingStrategy(TradingStrategy):
    name = 'longoption'

    def _maintenance(self) -> List:
        pass

    @staticmethod
    def find_option(options: List, strike_price: float) -> Dict:
        return next(option for option in options if float(option['strike_price']) == strike_price)

    def get_option(self, symbol: str, option_type: str, expiration_date: str, strike_price: float) -> Dict:
        options = filter_option_type(self.broker.get_options(symbol), option_type)
        options = self.broker.filter_options(options, [expiration_date])
        if not options:
            raise TradeDateException(
                f"No options for {symbol} found with the provided expiration date '{expiration_date}'.")
        options = self.broker.get_options_data(options)

        try:
            return self.find_option(options, strike_price)
        except StopIteration:
            raise TradeException(f"Could not find option with strike price {strike_price}")

    @staticmethod
    def validate_trade(option_type: str, allocation_dollars: int, allocation_percent: float,
                       expiration_date: str, days_out: int, strike_price: float) -> None:
        if option_type not in option_types:
            raise TradeConfigException("Option type must be one of 'call' or 'put'.")

        if not allocation_dollars >= 0:
            raise TradeConfigException("Allocation dollar amount must be positive.")

        if allocation_percent and not 0 < allocation_percent <= 100:
            raise TradeConfigException("Allocation percent must be > 0 and <= 100.")

        if expiration_date and not re.search(DATE_REGEX, expiration_date):
            raise TradeConfigException("Expiration date format must be YYYY-MM-DD.")

        if not 0 <= days_out < 1000:
            raise TradeConfigException("Days out value is not valid.")

        if not strike_price > 0:
            raise TradeConfigException("Invalid strike price.")

        if allocation_percent and allocation_dollars:
            raise TradeConfigException("Cannot supply both percentage and value for allocation.")

    def make_trade(self, symbol: str, option_type: str, strike_price: float, expiration_date: str = "",
                   allocation_percent: int = 0, allocation_dollars: int = 0, days_out: int = 0,
                   open_criteria: List = [], close_criteria: List = []):
        self.validate_trade(option_type, allocation_dollars, allocation_percent, expiration_date, days_out,
                            strike_price)
        symbol = symbol.upper()
        quote = self.broker.get_quote(symbol)
        date = self.broker.date
        if not quote:
            raise TradeException("Error getting quote for " + symbol)

        if open_criteria and not self.evaluate_criteria(open_criteria,
                                                        date=date.timestamp(),
                                                        price=quote):
            return {'status': 'deferred'}

        if days_out:
            option = None
            offset = 0
            while not option:
                td1 = get_offset_date(self.broker, days_out + offset)
                td2 = get_offset_date(self.broker, days_out - offset)
                for date in (td1, td2):
                    try:
                        option = self.get_option(symbol, option_type, date, strike_price)
                        break
                    except TradeDateException:
                        pass
                offset += 1
                if offset > 5:
                    raise TradeDateException("Couldn't find a valid expiration date in range.")
        else:
            option = self.get_option(symbol, option_type, expiration_date, strike_price)
        allocation = get_allocation(self.broker, allocation_percent) if allocation_percent else allocation_dollars
        price = option['mark_price']
        quantity = int(allocation / (price * 100))

        if not quantity:
            raise TradeException("Trade quantity equals 0.")

        # Broker determines "side" from the legs
        option["side"] = "buy"
        option_order = self.broker.options_transact([option], 'debit', price, quantity, 'open')
        self.save_order(option_order, [option], close_criteria=close_criteria, price=price, quantity=quantity,
                        expires=expiration_date)

        self.log("[{}]: Bought {} in {} with quantity {} and price {}.".format(
            option_order.id,
            option_type,
            symbol,
            quantity,
            round(price * 100, 2)))
        return {'status': 'placed', 'quantity': quantity, 'price': round(price * 100, 2)}

    def close_position(self, position: str, data: Dict, legs: List, reason: str):
        pass

