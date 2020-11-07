#!/usr/bin/env python3
import datetime
import random

from scipy import stats

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.misc import init_script, cli
from magictrade.strategy.optionseller import OptionSellerTradingStrategy
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades

NAME = "Linear Slope"
TICKERS = ({
    'ADBE': {'slope_len': 10, 'delta': [25, 35]},
    'CMG': {'slope_len': 5, 'delta': [15, 27]},
})


# CMG
# When LinRegSlope 5 of SMA 20 > 0 AND ClosePrice > SMA 20
#
# Enter PCS @ 15-27 delta, 35-45 DTE
#
# Close at 50% profit.


# ADBE
# When LinRegSlope 10 of SMA 20 > 0 AND ClosePrice > SMA 20
#
# Enter PCS @ 25-35 delta (or 20-30 delta for more conservative), 35-45 DTE
#
# Close at 50% profit.

def check_signals(ticker: str, slope_len: int, sma_len: int) -> bool:
    quote = FinnhubDataSource.get_quote(ticker)
    closes = FinnhubDataSource.get_historic_close(ticker, sma_len + 20)[-sma_len:]
    closes[-1] = quote  # ensure latest data is used
    slope = stats.linregress(range(slope_len), closes[-slope_len:]).slope
    return slope > 0.00 and quote > sum(closes[-20:]) / 20


def main(args):
    init_script(args, NAME)
    trade_queue = RedisTradeQueue(args.trade_queue)
    positions = set()
    try:
        if args.account_id:
            positions = {[t['data']['symbol'] for t in get_all_trades(args.account_id)]}
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
    for ticker, config in random.sample(TICKERS, k=args.ticker_count or len(TICKERS)):
        if trade_count >= args.trade_count:
            break
        if ticker in positions:
            print(f"{ticker} already in positions; skipping...")
            continue
        # Check entry rule
        if not check_signals(ticker, config['slope_len'], config.get('sma_len', 20)):
            if args.dry_run:
                print(f"Not {ticker} > MA_20 > MA_200; skipping...")
            continue

        if not args.dry_run:
            trade_queue.send_trade({
                "end": (close + datetime.timedelta(days=args.days)).timestamp(),
                "symbol": ticker,
                "allocation": args.allocation,
                "strategy": OptionSellerTradingStrategy.name,
                "days_out": 35,
                "leg_criteria": f"{config['delta'][0]} < leg.delta < {config['delta'][1]}",
                "trade_criteria": {"rr_delta": 1.00 if ticker == 'TLT' else 0.55},
                "close_criteria": [f"value and -1 * change >= {config.get('target', 50)}"],
                })
            trade_count += 1
    print(f"{trade_count} trades placed.")


if __name__ == "__main__":
    main(cli())
