from typing import Tuple, Dict

from magictrade import Position
from magictrade.backends import Backend, InsufficientFundsError, NonexistentAssetError


class PaperMoneyBackend(Backend):
    def __init__(self, balance: int = 1_000_000, data: Dict = {}, api_key: str = None):
        self._balance = balance
        self.equities = {}
        self.options = {}
        self.data = data
        self.api_key = api_key

    def get_quote(self, symbol: str, date: str = None) -> float:
        if self.data:
            if date:
                for key in self.data.get(symbol):
                    if "Time Series" in key:
                        return float(self.data.get(symbol)[key][date]['1. open'])
            else:
                return float(self.data.get(symbol)['Global Quote']['05. price'])

    @property
    def balance(self) -> float:
        return self._balance

    def options_transact(self, symbol: str, expiration: str, strike: float,
                         quantity: int, mode: str, direction: str) -> Tuple[str, Position]:
        pass

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        debit = self.get_quote(symbol) * quantity
        if self.balance - debit < 0:
            raise InsufficientFundsError()
        self._balance -= debit
        if self.equities.get(symbol):
            self.equities[symbol].quantity += quantity
            self.equities[symbol].cost += quantity
        else:
            self.equities[symbol] = Position(symbol, debit, quantity, self)
        return 'success', self.equities[symbol]

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        position = self.equities.get(symbol)
        if not position or position.quantity < quantity:
            raise NonexistentAssetError()
        credit = self.get_quote(symbol) * quantity
        self._balance -= credit
        position.quantity -= quantity
        position.cost -= credit
        return 'success', position
