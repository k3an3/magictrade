from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict

from magictrade import storage
from magictrade.broker import Broker
from magictrade.strategy.registry import strategies


def load_strategies():
    from magictrade.utils import import_modules
    import_modules(__file__, 'strategy')


class TradingStrategy(ABC):
    def __init__(self, broker: Broker):
        self.broker = broker

    def get_name(self):
        return "{}-{}".format(self.name, self.broker.account_id)

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

    @staticmethod
    def check_positions(legs: List, options: Dict) -> Dict:
        for leg in legs:
            if not leg['option'] in options:
                return leg

    def get_current_positions(self):
        positions = storage.lrange(self.get_name() + ":positions", 0, -1)
        if not positions:
            return
        owned_options = self.broker.options_positions()

        for position in positions:
            data = storage.hgetall("{}:{}".format(self.get_name(), position))
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
                legs.append(storage.hgetall("{}:leg:{}".format(self.get_name(), leg)))
            # Make sure we still own all legs, else abandon management of this position.
            if self.check_positions(legs, owned_options):
                self.delete_position(position)
                self.log("[{}]: Orphaned position {}-{} due to missing leg.".format(position, data['symbol'],
                                                                                    data['strategy'], ))
                continue
            yield position, data, legs

    def save_order(self, option_order: Dict, legs: List, order_data: Dict = {}, **kwargs):
        storage.lpush(self.get_name() + ":positions", option_order["id"])
        storage.lpush(self.get_name() + ":all_positions", option_order["id"])
        storage.hmset("{}:{}".format(self.get_name(), option_order["id"]),
                      {
                          'time': datetime.now().timestamp(),
                          **kwargs,
                          **order_data,
                      })
        for leg in option_order["legs"]:
            storage.lpush("{}:{}:legs".format(self.get_name(), option_order["id"]),
                          leg["id"])
            leg.pop('executions', None)
            storage.hmset("{}:leg:{}".format(self.get_name(), leg["id"]), leg)
        storage.set("{}:raw:{}".format(self.get_name(), option_order["id"]), str(legs))


class TradeException(Exception):
    pass


class TradeConfigException(TradeException):
    pass


class NoValidLegException(TradeException):
    pass
