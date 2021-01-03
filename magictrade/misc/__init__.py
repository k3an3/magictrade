from typing import List

from magictrade.trade_queue import RedisTradeQueue


def method_from_name(class_, method_name: str):
    """
    Given an imported class, return the given method pointer.
    :param class_: An imported class containing the method.
    :param method_name: The method name to find.
    :return: The method pointer
    """
    try:
        return getattr(class_, method_name)
    except AttributeError:
        raise NotImplementedError()


class MultiTradeQueue(RedisTradeQueue):
    def __init__(self, queues: List[RedisTradeQueue], single_return: bool = False):
        self.queues = queues
        self.single_return = single_return

    def __getattr__(self, item):
        if item == 'queues':
            return self.queues
        elif item == "queue_name":
            return self.queues[0].queue_name

        def _method(*args, **kwargs):
            results = []
            for queue in self.queues:
                results.append(method_from_name(queue, item)(*args, **kwargs))
            return results[0] if self.single_return else results

        return _method
