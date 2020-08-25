#!/usr/bin/env python3
import datetime
import random
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from time import sleep

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.strategy.bollinger import BollingerBendStrategy, INDEX
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades, bool_as_str

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
    try:
        if args.account_id:
            positions = set([t['data']['symbol'] for t in get_all_trades(args.account_id)])
    except AttributeError:
        pass

    # Check entry rule
    # the API considers weekends/holidays as days, so overshoot with the amount of days requested
    index_quote = FinnhubDataSource.get_quote(INDEX)
    index_200 = FinnhubDataSource.get_historic_close(INDEX, 300)[-200:]
    index_200[-1] = index_quote  # ensure latest data is used
    if index_quote < sum(index_200) / 200:
        print(f"{INDEX} not above 200 MA; aborting...")
        exit(0)

    now = datetime.datetime.now()
    close = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=16, minute=0, second=0, microsecond=0)
    for ticker in random.sample(TICKERS, k=args.trade_count or len(TICKERS)):
        if ticker in positions:
            continue

        # Calculations
        historic_closes = FinnhubDataSource.get_historic_close(ticker, 35)

        signal_1, signal_2, signal_3 = BollingerBendStrategy.check_signals(historic_closes)

        if signal_1 or signal_2 or signal_3:
            tq.send_trade({
                "dry_run": bool_as_str(args.dry_run),
                "end": close.timestamp(),
                "symbol": ticker,
                "allocation": args.allocation,
                "strategy": BollingerBendStrategy.name,
                "signal_1": bool_as_str(signal_1),
                "signal_2": bool_as_str(signal_2),
                "signal_3": bool_as_str(signal_3),
            })
        # API has 60 calls/minute limit
        sleep(1)


def cli():
    parser = ArgumentParser(description="Place Bollinger Bend trades.",
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--trade-queue', required=True, help="Name of the magictrade queue to add trades to.")
    parser.add_argument('-d', '--dry-run', action="store_true", help="Set the dry run flag to tell the backend to "
                                                                     "check if trades are "
                                                                     "suitable, but shouldn't be placed.")
    parser.add_argument('-c', '--trade-count', default=0, type=int,
                        help="Max number of trades to place. 0 for unlimited.")
    parser.add_argument('-l', '--allocation', type=int, default=1, help="Allocation percentage for each trade")
    parser.add_argument('-r', '--random-sleep', type=int, nargs=2, metavar=('min', 'max'),
                        help="Range of seconds to randomly sleep before running.")
    parser.add_argument('-a', '--account-id', help='If set, will check existing trades to avoid securities '
                                                   'with active trades.')
    main(parser.parse_args())


if __name__ == "__main__":
    cli()
