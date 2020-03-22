import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

from py_expression_eval import Parser

from magictrade import storage
from magictrade.broker import Broker
from magictrade.securities import OptionOrder
from magictrade.strategy.registry import strategies
from magictrade.utils import get_monthly_option, date_format


def load_strategies():
    from magictrade.utils import import_modules
    import_modules(__file__, 'strategy')


class TradingStrategy(ABC):
    name = 'tradingstrategy'
   
    def __init__(self, broker: Broker):
        self.broker = broker

    def init_strategy(self, symbol: str, open_criteria: List = []) -> Tuple:
        symbol = symbol.upper()
        quote = self.broker.get_quote(symbol)
        if not quote:
            raise TradeException("Error getting quote for " + symbol)

        if open_criteria and not self.evaluate_criteria(open_criteria,
                                                        date=self.broker.date.timestamp(),
                                                        price=quote):
            return quote, [], {'status': 'deferred'}

        options = self.broker.get_options(symbol)
        if not options:
            raise NoTradeException(f"No options found for {symbol}.")

        return quote, options, None

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

    def find_exp_date(self, config: Dict, options: List, timeline: int = 0, days_out: int = 0, monthly: bool = False,
                      exp_date: str = None):
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
            yield target_date, self.broker.get_options_data(options_on_date)

    def get_name(self):
        return "{}-{}".format(self.name, self.broker.account_id)

    @abstractmethod
    def maintenance(self) -> List:
        pass

    @abstractmethod
    def make_trade(self, symbol: str, *args, **kwargs):
        pass

    def log(self, msg: str) -> None:
        storage.lpush(self.get_name() + ":log", "{} {}".format(datetime.now().timestamp(), msg))

    def delete_position(self, trade_id: str) -> None:
        storage.lrem("{}:positions".format(self.get_name()), 0, trade_id)
        for leg in storage.lrange("{}:{}:legs".format(self.get_name(), trade_id), 0, -1):
            storage.delete("{}:leg:{}".format(self.get_name(), leg))
        storage.delete("{}:{}:legs".format(self.get_name(), trade_id))
        # consider not deleting this one for archival purposes
        storage.delete("{}:{}".format(self.get_name(), trade_id))

    def check_positions(self, legs: List, options: Dict) -> Dict:
        for leg in legs:
            if not self.broker.leg_in_options(leg, options):
                return leg

    def get_current_positions(self):
        positions = storage.lrange(self.get_name() + ":positions", 0, -1)
        if not positions:
            return
        owned_options = self.broker.options_positions()

        for position in positions:
            data = storage.hgetall("{}:{}".format(self.get_name(), position))
            try:
                data['close_criteria'] = json.loads(data['close_criteria'])
            except KeyError:
                pass
            # Temporary fix: the trade might not have filled yet
            try:
                time_placed = datetime.fromtimestamp(float(data['time']))
            except (KeyError, ValueError):
                time_placed = datetime.fromtimestamp(0)
            if time_placed.date() == datetime.today().date():
                continue
            leg_ids = storage.lrange("{}:{}:legs".format(self.get_name(), position), 0, -1)
            legs = []
            for leg in leg_ids:
                legs.append(self.broker.option(storage.hgetall("{}:leg:{}".format(self.get_name(), leg))))
            # Make sure we still own all legs, else abandon management of this position.
            if self.check_positions(legs, owned_options):
                self.delete_position(position)
                self.log("[{}]: Orphaned position {}-{} due to missing leg.".format(position, data['symbol'],
                                                                                    data['strategy'], ))
                continue
            yield position, data, legs

    def save_order(self, option_order: OptionOrder, legs: List, order_data: Dict = {},
                   close_criteria: Dict = {}, **kwargs):
        if close_criteria:
            kwargs['close_criteria'] = json.dumps(close_criteria)
        storage.lpush(self.get_name() + ":positions", option_order.id)
        storage.lpush(self.get_name() + ":all_positions", option_order.id)
        storage.hmset("{}:{}".format(self.get_name(), option_order.id),
                      {
                          'time': datetime.now().timestamp(),
                          **kwargs,
                          **order_data,
                      })
        for leg in option_order.legs:
            storage.lpush("{}:{}:legs".format(self.get_name(), option_order.id),
                          leg["id"])
            leg.pop('executions', None)
            storage.hmset("{}:leg:{}".format(self.get_name(), leg["id"]), leg)
        storage.set("{}:raw:{}".format(self.get_name(), option_order.id), str(legs))

    @staticmethod
    def evaluate_criteria(criteria, **kwargs) -> bool:
        parser = Parser()
        eval_result = None
        for criterion in criteria:
            try:
                result = parser.parse(criterion['expr']).evaluate(kwargs)
            except KeyError:
                raise TradeCriteriaException("No criterion expression provided.")
            except Exception as e:
                raise TradeCriteriaException(str(e))
            if eval_result is None:
                eval_result = result
            elif criterion.get('operation', 'and') == 'and':
                eval_result &= result
            elif criterion.get('operation', 'and') == 'or':
                eval_result |= result
        return eval_result


def filter_option_type(options: List, o_type: str):
    return [o for o in options if o["type"] == o_type]


class TradeException(Exception):
    """
    General exception class for all exceptions raised during processing and making of trades.
    """
    pass


class NoTradeException(Exception):
    """
    Exceptions during processing and making of trades that are beyond the application's control, and should not be
    treated as an error.
    """
    pass


class TradeCriteriaException(TradeException):
    pass


class TradeDateException(TradeException):
    pass


class TradeConfigException(TradeException):
    pass


class NoValidLegException(TradeException):
    pass
