import argparse

from magictrade import storage
from magictrade.utils import send_trade

default_queue_name = 'oatrading-queue'


def handle_trade(args):
    if args.days_out and args.timeline:
        print("Can't use timeline with days_out. Aborting.")
        raise SystemExit

    queue_name = args.queue_name
    args = vars(args)
    args.pop('func')
    args.pop('cmd')
    args.pop('queue_name')
    identifier = send_trade(queue_name, args)
    print("Placed trade {} with data:\n{}".format(identifier, args))


def handle_check(args):
    status = storage.get("{}:status:{}".format(args.queue_name, args.identifier))
    print("Returned status: '{}'".format(status))


def handle_list(args):
    for identifier in storage.lrange(args.queue_name, 0, -1):
        print(identifier, ":", storage.hgetall("{}:{}".format(args.queue_name, identifier)))


def cli():
    parser = argparse.ArgumentParser(description='Talk to magictrade daemon.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(help='Valid subcommands:', dest='cmd', required=True)
    list_parser = subparsers.add_parser('list', aliases=['l'], help='List pending trades.')
    trade_parser = subparsers.add_parser('trade', aliases=['t'], help='Place a trade',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    check_parser = subparsers.add_parser('check', aliases=['c'], help='Check status of a trade')
    check_parser.set_defaults(func=handle_check)
    trade_parser.set_defaults(func=handle_trade)
    list_parser.set_defaults(func=handle_list)
    check_parser.add_argument('identifier', help='Trade identifier returned by this tool when placing a trade')
    trade_parser.add_argument('symbol', help="Symbol to trade. e.g. \"SPY\"")
    trade_parser.add_argument('-d', '--direction', default='neutral', dest='direction',
                              choices=('bullish', 'bearish', 'neutral'), help='Type of trade to make')
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
