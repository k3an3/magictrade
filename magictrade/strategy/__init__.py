from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict

from magictrade import Broker, storage


class TradingStrategy(ABC):
    def __init__(self, broker: Broker):
        self.broker = broker

    def get_name(self):
        return "{}-{}".format(self.name, self.broker.account_id)

    @abstractmethod
    def make_trade(self, symbol: str):
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
        account_positions = self.broker.options_positions()
        owned_options = {option['option']: option for option in account_positions}

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


def filter_option_type(options: List, o_type: str):
    return [o for o in options if o["type"] == o_type]


class TradeException(Exception):
    pass


class NoValidLegException(TradeException):
    pass
