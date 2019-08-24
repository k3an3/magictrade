import datetime

from typing import Dict

from magictrade import storage


class TradeQueue:
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.index = 0
        self._stage = []

    def _data_name(self, identifer: str) -> str:
        return "{}:{}".format(self.queue_name, identifer)

    def __iter__(self):
        return storage.lrange(self.queue_name, 0, -1)

    def __next__(self):
        if self.index >= self.__len__():
            raise StopIteration
        result = storage.lindex(self.queue_name, self.index)
        self.index += 1
        return result

    def __len__(self):
        return storage.llen(self.queue_name)

    def __repr__(self):
        return self.__iter__()

    def set_data(self, identifier: str, trade: Dict):
        storage.hmset(self._data_name(identifier), trade)

    def add(self, identifier: str, trade: Dict):
        storage.lpush(self.queue_name, identifier)
        self.set_data(identifier, trade)

    def add_failed(self, identifier: str, error: str):
        storage.lpush(self.queue_name + "-failed", identifier)
        storage.set("{}:status:{}".format(self.queue_name, identifier), error)

    def stage_trade(self, identifier: str):
        self._stage.append(identifier)

    def pop(self):
        identifier = storage.rpop(self.queue_name)
        trade = self.get_data(identifier)
        return identifier, trade

    def get_data(self, identifier: str):
        return storage.hgetall(self._data_name(identifier))

    def get_allocation(self):
        return int(storage.get(self.queue_name + ":allocation")) or 0

    def set_current_usage(self, buying_power: float, balance: float):
        storage.set(self.queue_name + ":current_usage", f"{buying_power}/{balance}")

    def heartbeat(self):
        storage.set(self.queue_name + ":heartbeat", datetime.datetime.now().timestamp())
