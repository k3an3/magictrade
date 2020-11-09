#!/usr/bin/env python3
import datetime
import random

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.misc import init_script, cli
from magictrade.strategy.optionseller import OptionSellerTradingStrategy
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades

NAME = "SOP Bonds"
TICKERS = ('TLT', 'TLH', 'IEF', 'IEI', 'IGOV', 'EMB')

config = {
    'timeline': [35, 45],
    'target': 50,
    'direction': 'put',
    'width': 1,
}


def check_signals(ticker: str) -> bool:
    quote = FinnhubDataSource.get_quote(ticker)
    close_200 = FinnhubDataSource.get_historic_close(ticker, 300)[-200:]
    close_200[-1] = quote  # ensure latest data is used
    return quote > sum(close_200[-20:]) / 20 > sum(close_200) / 200


def main(args):
    init_script(args, NAME)
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
                "spread_width": config['width'],
                "sort_reverse": True,
                "direction": config['direction'],
                "sort_by": "delta",
                "days_out": sum(config['timeline']) // 2,
                "leg_criteria": f"{min_delta} < abs(delta) and abs(delta) < {max_delta + 0.9}",
                "trade_criteria": {"rr_delta": 1.00 if ticker == 'TLT' else 0.55},
                "close_criteria": [f"value and -1 * change >= {config.get('target', 50)}"],
            })
            trade_count += 1
    print(f"{trade_count} trades placed.")


if __name__ == "__main__":
    main(cli(NAME))
