import argparse
from datetime import datetime

from magictrade import storage

queue_name = 'oatrading-queue'


def cli():
    parser = argparse.ArgumentParser(description='Talk to magictrade.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('symbol', help="Symbol to trade. E.G. \"SPY\"")
    parser.add_argument('-d', '--direction', required=True, dest='direction',
                        choices=('bullish', 'bearish', 'neutral'), help='Type of trade to make.')
    #parser.add_argument('-q', '--quantity', type=int, default=1, dest='quantity', help='Number of contracts to trade.')
    parser.add_argument('-i', '--iv-rank', type=int, default=50, dest='iv_rank', help="Current IV ranking/percentile "
                                                                                      "of stock.")
    parser.add_argument('-a', '--allocation', type=int, default=3, dest='allocation', help='Percentage of portfolio, '
                                                                                           'in whole numbers, '
                                                                                           'to put up for the trade.')
    parser.add_argument('-t', '--timeline', type=int, default=50, dest='timeline', help="Percentage of strategy's "
                                                                                        "time range to target for "
                                                                                        "expiry.")
    parser.add_argument('-s', '--days-out', type=int, default=0, dest='days_out', help='Number of days to target, '
                                                                                       'cannot be used with timeline.')
    parser.add_argument('-w', '--spread-width', type=int, default=3, dest='spread_width', help='Width of spreads.')

    args = parser.parse_args()
    identifier = "{}-{}".format(args.symbol, datetime.now().strftime("%Y%m%d%H%M%S"))
    storage.lpush(queue_name, identifier)

    if args.days_out and args.timeline:
        print("Can't use timeline with days_out. Aborting.")
        raise SystemExit

    storage.hmset("{}:{}".format(queue_name, identifier), vars(args))


if __name__ == "__main__":
    cli()
