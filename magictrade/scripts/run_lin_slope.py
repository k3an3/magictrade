#!/usr/bin/env python3
import datetime
import random
from typing import List

from scipy import stats

from magictrade.datasource.stock import FinnhubDataSource
from magictrade.scripts import init_script, cli
from magictrade.strategy.optionseller import OptionSellerTradingStrategy
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades, bool_as_str

NAME = "Linear Slope"
DEFAULT_SLOPE_PERIOD = 5
DEFAULT_SMA_PERIOD = 20
DEFAULT_DTE = 40
DEFAULT_RR = 0.60

TICKERS = {
    'AAPL': {'delta': [20, 32]},
    'ADBE': {'delta': [30, 40]},
    'AMZN': {'delta': [30, 40], 'dte': 20, 'slope': 10, 'sma': 50},
    'CMG': {'delta': [17, 27]},
    'COST': {'delta': [17, 27], 'sma': 14},
    'CRM': {'delta': [17, 27], 'sma': 50, 'slope': 10},
    'GOOGL': {'delta': [15, 25], 'dte': 30, 'sma': 30},
    'HD': {'delta': [20, 32], 'sma': 14},
    'IBM': {'delta': [15, 25], 'sma': 50, 'slope': 10},
    'INTC': {'delta': [17, 27], 'sma': 30},
    'LOW': {'delta': [17, 27], 'sma': 14},
    'MA': {'delta': [20, 32]},
    'NFLX': {'delta': [14, 24]},
    'NVDA': {'delta': [30, 40], 'sma': 14, 'dte': 20},
    'PG': {'delta': [20, 32]},
    'QCOM': {'delta': [20, 32], 'sma': 50, 'slope': 10},
    'SBUX': {'delta': [20, 32], 'sma': 14, 'rr': 0.85},
    'SPY': {'delta': [17, 27], 'sma': 14},
    'UNH': {'delta': [20, 32], 'sma': 50, 'slope': 10},
    'UNP': {'delta': [30, 40]},
    'V': {'delta': [20, 32]},
    'YUM': {'delta': [25, 35]},
}


def get_n_sma(quotes: List[float], slope_period: int, sma_period: int) -> float:
    results = []
    for i in range(-1 * slope_period, 0, 1):
        if i == -1:
            end = None
        else:
            end = i + 1
        results.append(sum(quotes[i - sma_period + 1:end]) / sma_period)
    return results


def handle_check_signals(ticker: str, slope_period: int, sma_period: int) -> bool:
    quote = FinnhubDataSource.get_quote(ticker)
    closes = FinnhubDataSource.get_historic_close(ticker, sma_period + 50)[-sma_period:]
    return check_signals(quote, closes, slope_period, sma_period)


def check_signals(quote: float, closes: List[float], slope_period: int, sma_period: int) -> bool:
    closes[-1] = quote  # ensure latest data is used
    slope = stats.linregress(range(slope_period), get_n_sma(closes, slope_period, sma_period)).slope
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
    for ticker, config in random.sample(TICKERS.items(),
                                        k=min(args.ticker_count, len(TICKERS)) if args.ticker_count else len(TICKERS)):
        if trade_count >= args.trade_count:
            break
        if ticker in positions:
            print(f"{ticker} already in positions; skipping...")
            continue
        # Check entry rule
        if not handle_check_signals(ticker, config.get('slope', DEFAULT_SLOPE_PERIOD),
                                    config.get('sma', DEFAULT_SMA_PERIOD)):
            if args.dry_run:
                print(f"Not {ticker} > MA_20 > MA_200; skipping...")
            continue

        if not args.dry_run:
            trade_queue.send_trade({
                "end": (close + datetime.timedelta(days=args.days)).timestamp(),
                "symbol": ticker,
                "allocation": args.allocation,
                "strategy": OptionSellerTradingStrategy.name,
                "days_out": config.get('dte', DEFAULT_DTE),
                "sort_reverse": bool_as_str(True),
                "direction": "put",
                "sort_by": "delta",
                "leg_criteria": f"{config['delta'][0]} < abs(delta) * 100 and abs(delta) * 100 < {config['delta'][1] + 0.9}",
                "trade_criteria": {"rr_delta": 1},
                "close_criteria": [f"value and -1 * change >= {config.get('target', 50)}"],
            })
            trade_count += 1
    print(f"{trade_count} trades placed.")


def init():
    main(cli(NAME))


if __name__ == "__main__":
    init()
