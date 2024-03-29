#!/usr/bin/env python3
import datetime
import random
from statistics import pstdev
from typing import List

import sys
from time import sleep

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.scripts import init_script, cli, get_parser
from magictrade.strategy.optionseller import OptionSellerTradingStrategy
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades, bool_as_str

NAME = "Bollinger Bend"
TICKERS = ("AAPL", "ABBV", "ADBE", "AMAT", "AMD", "AMGN", "AMZN", "ATVI",
           "AVGO", "AXP", "AZO", "BA", "BABA", "BAC", "BIDU", "BKNG", "BMY",
           "BP", "BYND", "C", "CAT", "CGC", "CMCSA", "CMG", "COST", "CRM",
           "CSCO", "CVS", "CVX", "DAL", "DE", "DIS", "DOW", "DRI", "EXPE",
           "FB", "FDX", "FIVE", "GILD", "GIS", "GOOGL", "GS", "HD", "HON",
           "IBM", "INTC", "ISRG", "JNJ", "JPM", "KMX", "KO", "LMT", "LOW",
           "LRCX", "LULU", "LVS", "LYFT", "MA", "MCD", "MELI", "MMM", "MRK",
           "MS", "MSFT", "MU", "NFLX", "NKE", "NOC", "NVDA", "NXPI", "PEP",
           "PFE", "PG", "PXD", "PYPL", "QCOM", "RH", "ROKU", "RTX", "SBUX",
           "SHOP", "SQ", "SWKS", "T", "TGT", "TRV", "TSLA", "TSN", "TTD",
           "TWLO", "TWTR", "TXN", "UBER", "ULTA", "UNH", "UNP", "UPS", "URI",
           "V", "VZ", "WBA", "WDAY", "WDC", "WMT", "WYNN", "XOM", "YUM")
OPTIMIZED_DELTA = {
    'AAPL': (15, 25),
    'ADBE': (20, 30),
    'AVGO': (35, 45),
    'CAT': (35, 45),
    'CMG': (20, 30),
    'COST': (20, 30),
    'DE': (20, 30),
    'EXPE': (20, 30),
    'GOOGL': (20, 30),
    'HD': (20, 30),
    'MSFT': (20, 30),
    'MU': (20, 32),
    'NFLX': (20, 30),
    'PG': (20, 30),
    'T': (15, 25),
    'MSFT': (20, 30),
    'MSFT': (20, 30),
}
INDEX = 'SPY'
config = {
    'timeline': [35, 45],
    'target': 50,
    'direction': 'put',
    'width': 1,
    'rr_delta': 1.00,
}
SIGNAL_1_2_DELTA = (20, 30)
SIGNAL_3_DELTA = (15, 25)


def check_signals(historic_closes: List[float]):
    ma_20 = sum(historic_closes[-20:]) / 20
    prev_ma_20 = sum(historic_closes[-21:-1]) / 20
    ma_3 = sum(historic_closes[-3:]) / 3
    u_bb_3_3 = ma_3 + pstdev(historic_closes[-3:]) * 3
    l_bb_20_1 = ma_20 - pstdev(historic_closes[-20:])
    u_bb_3_1 = ma_3 + pstdev(historic_closes[-3:])
    prev_u_bb_3_1 = sum(historic_closes[-4:-1]) / 3 + pstdev(
        historic_closes[-4:-1])
    l_bb_3_3 = ma_3 - pstdev(historic_closes[-3:]) * 3
    u_bb_20_1 = ma_20 + pstdev(historic_closes[-20:])

    # Signals
    signal_1 = u_bb_3_3 < l_bb_20_1
    signal_2 = u_bb_3_1 < ma_20 * 0.99 and prev_u_bb_3_1 > prev_ma_20 * 0.99
    signal_3 = l_bb_3_3 > u_bb_20_1

    return signal_1, signal_2, signal_3


def main(args):
    init_script(args, NAME)

    trade_queue = RedisTradeQueue(args.trade_queue)
    positions = set()
    try:
        if args.account_id:
            positions = set(
                [t['data']['symbol'] for t in get_all_trades(args.account_id)])
    except AttributeError:
        pass

    # Check entry rule
    # the API considers weekends/holidays as days, so overshoot with the amount of days requested
    index_quote = FinnhubDataSource.get_quote(INDEX)
    index_200 = FinnhubDataSource.get_historic_close(INDEX, 300)[-200:]
    index_200[-1] = index_quote  # ensure latest data is used
    if index_quote < sum(index_200) / 200:
        print(f"{INDEX} not above 200 MA; aborting...")
        sys.exit(0)

    now = datetime.datetime.now()
    close = datetime.datetime(year=now.year,
                              month=now.month,
                              day=now.day,
                              hour=16,
                              minute=0,
                              second=0,
                              microsecond=0)
    trade_count = 0
    tickers = args.symbols or TICKERS
    for ticker in random.sample(tickers, k=min(args.ticker_count, len(tickers))):
        if trade_count >= args.trade_count:
            break
        if ticker in positions:
            print(f"{ticker} already in positions; skipping...")
            continue

        # Calculations
        historic_closes = FinnhubDataSource.get_historic_close(ticker, 35)
        while True:
            try:
                historic_closes[-1] = FinnhubDataSource.get_quote(ticker)  # ensure latest data is used
            except KeyError:
                # Handle API rate limiting
                sleep(60)
            else:
                break

        if not historic_closes:
            print(f"No ticker history for {ticker}; skipping...")
            continue
        signal_1, signal_2, signal_3 = check_signals(
            historic_closes)
        print(f"{ticker: <5}: {signal_1=}, {signal_2=}, {signal_3=}")

        if signal_1 or signal_2:
            min_delta, max_delta = OPTIMIZED_DELTA.get(ticker, SIGNAL_1_2_DELTA)
        elif signal_3:
            min_delta, max_delta = SIGNAL_3_DELTA

        if not args.dry_run and (signal_1 or signal_2 or signal_3):
            trade_queue.send_trade({
                "end": (close + datetime.timedelta(days=args.days)).timestamp(),
                "symbol": ticker,
                "allocation": args.allocation,
                "strategy": OptionSellerTradingStrategy.name,
                "spread_width": config['width'],
                "days_out": sum(config['timeline']) // 2,
                "sort_reverse": bool_as_str(True),
                "direction": config['direction'],
                "sort_by": "delta",
                "trade_criteria": {"rr_delta": config['rr_delta']},
                "leg_criteria": f"{min_delta} < abs(delta) * 100 and abs(delta) * 100 < {max_delta + 0.9}",
                "close_criteria": [
                    f"value and -1 * change >= {config.get('target', 50)}",
                ],
            })
            trade_count += 1
        # API has 60 calls/minute limit
        sleep(0 if args.ticker_count < 60 else 1)
    print(f"{trade_count} trades placed.")


def init():
    parser = get_parser(NAME)
    parser.add_argument('-s', '--symbols', nargs="*", help="One or more tickers to check for making a trade.")
    main(cli(NAME, parser))


if __name__ == "__main__":
    init()
