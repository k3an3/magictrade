import datetime

from magictrade.broker import Broker

#storage = redis.StrictRedis(db=0, decode_responses=True)


class Position:
    def __init__(self, symbol: str, cost: float, quantity: int, backend: Broker, type: str = "equity",
                 strike: float = None, exp_date: str = None):
        self.symbol = symbol
        self.cost = cost
        self.quantity = quantity
        self.type = type
        self.strike = strike
        self.exp_date = exp_date
        self.date = datetime.datetime.now()
        self.backend = backend

    def _transact(self, quantity, mode: str):
        if self.type in ('call', 'put'):
            self.backend.options_transact(self.symbol, self.exp_date, self.strike, quantity, self.type, mode)
        else:
            if mode == 'buy':
                self.backend.buy(self.symbol, quantity)
            elif mode == 'sell':
                self.backend.sell(self.symbol, quantity)

    def buy(self, quantity):
        self._transact(quantity, 'buy')

    def sell(self, quantity):
        self._transact(quantity, 'sell')

    @property
    def get_value(self) -> float:
        return self.quantity * self.backend.get_quote(self.symbol)
