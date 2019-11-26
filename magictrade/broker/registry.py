brokers = {}


def register_broker(broker):
    brokers[broker.name] = broker
    return broker
