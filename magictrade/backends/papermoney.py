from typing import Tuple

from magictrade import Position
from magictrade.backends import Backend


class PaperMoneyBackend(Backend):
    def __init__(self, balance: int = 1_000_000):
        self.balance = balance

    def get_quote(self, symbol) -> float:
        pass

    @property
    def balance(self) -> float:
        pass

    def options_transact(self, symbol: str, expiration: str, strike: float,
                         quantity: int, mode: str, direction: str) -> Tuple[str, Position]:
        pass

    def buy(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        pass

    def sell(self, symbol: str, quantity: int) -> Tuple[str, Position]:
        pass
