strategies = {}


def register_strategy(strategy):
    strategies[strategy.name] = strategy
    return strategy
