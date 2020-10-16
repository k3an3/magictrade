#!/usr/bin/env python3
import datetime
import random
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from statistics import pstdev
from typing import List

import sys
from time import sleep

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.misc import init_script, get_parser
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
    'strategy': 'credit_spread',
}
SIGNAL_1_2_DELTA = (100 - 20, 100 - 30.9)
SIGNAL_3_DELTA = (100 - 15, 100 - 25)


@staticmethod
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
    for ticker in random.sample(TICKERS, k=args.ticker_count or len(TICKERS)):
        if trade_count >= args.trade_count:
            break
        if ticker in positions:
            print(f"{ticker} already in positions; skipping...")
            continue

        # Calculations
        historic_closes = FinnhubDataSource.get_historic_close(ticker, 35)
        # TODO: update latest value with quote?
        # historic_closes[-1] = FinnhubDataSource.get_quote(ticker)  # ensure latest data is used

        if not historic_closes:
            print(f"No ticker history for {ticker}; skipping...")
            continue
        signal_1, signal_2, signal_3 = check_signals(
            historic_closes)
        print(f"{ticker: <5}: {signal_1=}, {signal_2=}, {signal_3=}")

        # Note that "probability" is actually delta for our TD impl.
        if signal_1 or signal_2:
            max_delta, min_delta = OPTIMIZED_DELTA.get(ticker, SIGNAL_1_2_DELTA)
        elif signal_3:
            max_delta, min_delta = SIGNAL_3_DELTA

        if not args.dry_run and (signal_1 or signal_2 or signal_3):
            trade_queue.send_trade({
                "dry_run": bool_as_str(args.dry_run),
                "end": (close + datetime.timedelta(days=args.days)).timestamp(),
                "symbol": ticker,
                "allocation": args.allocation,
                "strategy": OptionSellerTradingStrategy.name,
                "leg_criteria": f"{min_delta} < leg.delta < {max_delta}",
            })
            trade_count += 1
        # API has 60 calls/minute limit
        sleep(1)
    print(f"{trade_count} trades placed.")


def cli():
    parser = get_parser(NAME)
    args = parser.parse_args()
    if not (args.dry_run or args.trade_queue):
        print("Error: Either --trade-queue or --dry-run are required.")
        parser.print_usage()
        sys.exit(1)
    main(args)


if __name__ == "__main__":
    cli()
