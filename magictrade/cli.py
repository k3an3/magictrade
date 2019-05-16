#!/usr/bin/env python3
import argparse
from datetime import datetime

from magictrade import storage

default_queue_name = 'oatrading-queue'


def handle_trade(args):
    if args.days_out and args.timeline:
        print("Can't use timeline with days_out. Aborting.")
        raise SystemExit

    identifier = "{}-{}".format(args.symbol, datetime.now().strftime("%Y%m%d%H%M%S"))
    queue_name = args.queue_name
    args = vars(args)
    args.pop('func')
    storage.hmset("{}:{}".format(queue_name, identifier), args)
    storage.lpush(queue_name, identifier)

    print("Placed trade {} with status:\n{}".format(identifier, args))


def handle_check(args):
    status = storage.get("{}:status:{}".format(args.queue_name, args.identifier))
    print("Returned status: '{}'".format(status))


def cli():
    parser = argparse.ArgumentParser(description='Talk to magictrade daemon.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(help='Valid subcommands:', dest='cmd', required=True)
    trade_parser = subparsers.add_parser('trade', aliases=['t'], help='Place a trade')
    trade_parser.set_defaults(func=handle_trade)
    check_parser = subparsers.add_parser('check', aliases=['c'], help='Check status of a trade')
    check_parser.set_defaults(func=handle_check)
    check_parser.add_argument('identifier', help='Trade identifier returned by this tool when placing a trade')
    trade_parser.add_argument('symbol', help="Symbol to trade. e.g. \"SPY\"")
    trade_parser.add_argument('-d', '--direction', required=True, dest='direction',
                              choices=('bullish', 'bearish', 'neutral'), help='Type of trade to make')
    # trade_parser.add_argument('-q', '--quantity', type=int, default=1, dest='quantity', help='Number of contracts
    # to trade')
    trade_parser.add_argument('-i', '--iv-rank', type=int, default=50, dest='iv_rank',
                              help="Current IV "
                                   "ranking/percentile "
                                   "of stock")
    trade_parser.add_argument('-a', '--allocation', type=float, default=3, dest='allocation',
                              help='Percentage of portfolio, '
                                   'in whole numbers, '
                                   'to put up for the trade')
    trade_parser.add_argument('-t', '--timeline', type=int, default=50, dest='timeline',
                              help="Percentage of strategy's "
                                   "time range to target for "
                                   "expiry")
    trade_parser.add_argument('-s', '--days-out', type=int, default=0, dest='days_out',
                              help='Number of days to target, '
                                   'cannot be used with timeline')
    trade_parser.add_argument('-w', '--spread-width', type=float, default=3, dest='spread_width',
                              help='Width of spreads')
    parser.add_argument('-q', '--queue-name', default=default_queue_name, dest='queue_name',
                        help='Redis queue name that the '
                             'daemon is reading from')

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
