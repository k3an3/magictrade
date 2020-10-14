#!/usr/bin/env python3
import datetime
import random
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import sys

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.misc import init_script
from magictrade.strategy.optionseller import OptionSellerTradingStrategy
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades

TICKERS = ('TLT', 'TLH', 'IEF', 'IEI', 'IGOV', 'EMB')


def check_signals(ticker: str) -> bool:
    quote = FinnhubDataSource.get_quote(ticker)
    ma200 = FinnhubDataSource.get_historic_close(ticker, 300)[-200:]
    ma200[-1] = quote  # ensure latest data is used
    ma20 = ma200[-20:]
    return quote > ma20 > ma200


def main(args):
    init_script(args, "SOP Bonds")
    trade_queue = RedisTradeQueue(args.trade_queue)
    positions = set()
    try:
        if args.account_id:
            positions = {t['data']['symbol'] for t in get_all_trades(args.account_id)}
            # TODO: make sure ticker wasn't placed in past 5 days
    except AttributeError:
        pass

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
        # Check entry rule
        if not check_signals(ticker):
            if args.dry_run:
                print(f"Not {ticker} > MA_20 > MA_200; skipping...")
            continue

        if not args.dry_run:
            min_delta = 20 if ticker == 'TLT' else 30
            max_delta = 31 if ticker == 'TLT' else 46 
            trade_queue.send_trade({
                "end": (close + datetime.timedelta(days=args.days)).timestamp(),
                "symbol": ticker,
                "allocation": args.allocation,
                "strategy": OptionSellerTradingStrategy.name,
                "days_out": 35,
                "leg_criteria": f"{min_delta} < leg.delta < {max_delta}",
            })
            trade_count += 1
    print(f"{trade_count} trades placed.")


def cli():
    parser = ArgumentParser(description="Place SOP Bond trades.",
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--trade-queue', help="Name of the magictrade queue to add trades to.")
    parser.add_argument('-d', '--dry-run', action="store_true", help="Set the dry run flag to check for trade "
                                                                     "signals, but not actually place trades.")
    parser.add_argument('-c', '--trade-count', default=0, type=int,
                        help="Max number of trades to place. 0 for unlimited.")
    parser.add_argument('-n', '--ticker-count', default=0, type=int,
                        help="Max number of tickers to consider. 0 for unlimited.")
    parser.add_argument('-l', '--allocation', type=int, default=1, help="Allocation percentage for each trade")
    parser.add_argument('-p', '--run-probability', type=int,
                        help="Probability (out of 100) that any trades should be placed on a given run.")
    parser.add_argument('-r', '--random-sleep', type=int, nargs=2, metavar=('min', 'max'),
                        help="Range of seconds to randomly sleep before running.")
    parser.add_argument('-a', '--account-id', help='If set, will check existing trades to avoid securities '
                                                   'with active trades.')
    parser.add_argument('-e', '--days', default=0, type=int, help="Place trades that are valid for this many days.")
    args = parser.parse_args()
    if not (args.dry_run or args.trade_queue):
        print("Error: Either --trade-queue or --dry-run are required.")
        parser.print_usage()
        sys.exit(1)
    main(args)


if __name__ == "__main__":
    cli()
