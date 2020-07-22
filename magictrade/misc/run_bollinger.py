#!/usr/bin/env python3
import datetime
import random
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from time import sleep

from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades

TICKERS = (
    "AAPL", "ABBV", "ADBE", "AMAT", "AMD", "AMGN", "AMZN", "ATVI", "AVGO", "AXP", "AZO", "BA", "BABA", "BAC", "BIDU",
    "BKNG", "BMY", "BP", "BYND", "C", "CAT", "CGC", "CMCSA", "CMG", "COST", "CRM", "CSCO", "CVS", "CVX", "DAL", "DE",
    "DIS", "DOW", "DRI", "EXPE", "FB", "FDX", "FIVE", "GILD", "GIS", "GOOGL", "GS", "HD", "HON", "IBM", "INTC", "ISRG",
    "JNJ", "JPM", "KMX", "KO", "LMT", "LOW", "LRCX", "LULU", "LVS", "LYFT", "MA", "MCD", "MELI", "MMM", "MRK", "MS",
    "MSFT", "MU", "NFLX", "NKE", "NOC", "NVDA", "NXPI", "PEP", "PFE", "PG", "PXD", "PYPL", "QCOM", "RH", "ROKU", "RTX",
    "SBUX", "SHOP", "SQ", "SWKS", "T", "TGT", "TRV", "TSLA", "TSN", "TTD", "TWLO", "TWTR", "TXN", "UBER", "ULTA", "UNH",
    "UNP", "UPS", "URI", "UTX", "V", "VZ", "WBA", "WDAY", "WDC", "WMT", "WYNN", "XOM", "YUM")


def main(args):
    if args.random_sleep:
        seconds = random.randint(*args.random_sleep)
        print(f"Sleeping for {seconds}s.")
        sleep(seconds)

    tq = RedisTradeQueue(args.trade_queue)
    positions = set()
    trade_count = 0
    try:
        if args.account_id:
            positions = set([t['data']['symbol'] for t in get_all_trades(args.account_id)])
    except AttributeError:
        pass

    close = datetime.datetime.now()
    close.hour = 16
    close.minute = 00
    close.second = 00
    tickers = random.sample(TICKERS, k=len(TICKERS))
    while not trade_count or trade_count < args.trade_count:
        ticker = tickers.pop()
        if ticker in positions:
            continue
        tq.send_trade({
            "dry_run": args.dry_run,
            "end": close.timestamp(),
            "symbol": ticker,
            "allocation": args.allocation,
        })
        if trade_count:
            trade_count += 1


def cli():
    parser = ArgumentParser(description="OptionAlpha toolbox integration for magictrade.",
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--trade-queue', help="Name of the magictrade queue to add trades to.")
    parser.add_argument('-d', '--dry-run', action="store_true", help="Set the dry run flag to tell the backend to "
                                                                     "check if trades are "
                                                                     "suitable, but shouldn't be placed.")
    parser.add_argument('-c', '--trade-count', type=int, help="Max number of trades to place.")
    parser.add_argument('-l', '--allocation', type=int, default=1, help="Allocation percentage for each trade")
    parser.add_argument('-r', '--random-sleep', type=int, nargs=2, metavar=('min', 'max'),
                        help="Range of seconds to randomly sleep before running.")
    parser.add_argument('-a', '--account-id', help='If set, will check existing trades to avoid securities '
                                                   'with active trades.')
    main(parser.parse_args())


if __name__ == "__main__":
    cli()
