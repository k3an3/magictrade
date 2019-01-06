import json
import os

from magictrade.backends.papermoney import PaperMoneyBackend

"3KODWEPB1ZR37OT7"

quotes = {
    'SPY': {
        "Global Quote": {
            "01. symbol": "SPY",
            "02. open": "247.5900",
            "03. high": "253.1100",
            "04. low": "247.1700",
            "05. price": "252.3900",
            "06. volume": "142628834",
            "07. latest trading day": "2019-01-04",
            "08. previous close": "244.2100",
            "09. change": "8.1800",
            "10. change percent": "3.3496%"
        },
    },
    'MSFT': {
        "Global Quote": {
            "01. symbol": "MSFT",
            "02. open": "99.7200",
            "03. high": "102.5100",
            "04. low": "98.9300",
            "05. price": "101.9300",
            "06. volume": "44060620",
            "07. latest trading day": "2019-01-04",
            "08. previous close": "97.4000",
            "09. change": "4.5300",
            "10. change percent": "4.6509%"
        },
    },
}

with open(os.path.join('tests', 'data', 'SPY_5min_intraday.json')) as f:
    dataset1 = json.loads(f.read())


class TestPaperMoney:
    def test_default_balance(self):
        pmb = PaperMoneyBackend()
        assert pmb.balance == 1_000_000

    def test_balance(self):
        pmb = PaperMoneyBackend(balance=12345)
        assert pmb.balance == 12345

    def test_quote(self):
        pmb = PaperMoneyBackend(data=quotes)
        assert pmb.get_quote('SPY') == 252.39

    def test_intraday_price(self):
        pmb = PaperMoneyBackend(data={'SPY': dataset1})
        assert pmb.get_quote('SPY', '2019-01-04 12:20:00') == 251.375

    def test_purchase_equity(self):
        pmb = PaperMoneyBackend(data=quotes)
        pmb.buy('SPY', 100)
        assert pmb.equities['SPY'].quantity == 100
        assert pmb.equities['SPY'].cost == 25_239

    def test_sell_equity(self):
        pmb = PaperMoneyBackend(data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 100)
        assert pmb.equities['SPY'].quantity == 0
        assert pmb.equities['SPY'].cost == 0

    def test_sell_equity_2(self):
        pmb = PaperMoneyBackend(data=quotes)
        pmb.buy('SPY', 100)
        pmb.sell('SPY', 50)
        assert pmb.equities['SPY'].quantity == 50
        assert round(pmb.equities['SPY'].cost, 2) == 25239 / 2

    def test_buy_sell_multiple(self):
        pmb = PaperMoneyBackend(data=quotes)
        pmb.buy('MSFT', 12)
        pmb.buy('SPY', 97)
        pmb.sell('MSFT', 5)
        pmb.sell('SPY', 50)
        assert pmb.equities['MSFT'].quantity == 7
        assert pmb.equities['MSFT'].cost == 713.51
        assert pmb.equities['SPY'].quantity == 47
        assert round(pmb.equities['SPY'].cost, 2) == 11862.33
