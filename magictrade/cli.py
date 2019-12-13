import argparse

from magictrade.trade_queue import TradeQueue


def handle_trade(args: argparse.Namespace, trade_queue: TradeQueue):
    if args.days_out and args.timeline:
        print("Can't use timeline with days_out. Aborting.")
        raise SystemExit

    args = vars(args)
    args.pop('func')
    args.pop('queue_name')
    identifier = trade_queue.send_trade(args)
    print("Placed trade {} with data:\n{}".format(identifier, args))


def handle_check(args: argparse.Namespace, trade_queue: TradeQueue):
    status = trade_queue.get_status(args.identifier)
    print("Returned status: '{}'".format(status))


def handle_list(args: argparse.Namespace, trade_queue: TradeQueue):
    for identifier in trade_queue:
        print(identifier, ":", trade_queue.get_data(identifier))


def cli():
    parser = argparse.ArgumentParser(description='Talk to magictrade daemon.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(help='Valid subcommands:', required=True)
    list_parser = subparsers.add_parser('list', aliases=['l'], help='List pending trades.')
    trade_parser = subparsers.add_parser('trade', aliases=['t'], help='Place a trade',
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    check_parser = subparsers.add_parser('check', aliases=['c'], help='Check status of a trade')
    check_parser.set_defaults(func=handle_check)
    trade_parser.set_defaults(func=handle_trade)
    list_parser.set_defaults(func=handle_list)
    check_parser.add_argument('identifier', help='Trade identifier returned by this tool when placing a trade')
    trade_parser.add_argument('symbol', help="Symbol to trade. e.g. \"SPY\"")
    trade_parser.add_argument('-d', '--direction', default='neutral',
                              choices=('bullish', 'bearish', 'neutral'), help='Type of trade to make')
    trade_parser.add_argument('--exp-date', help='Specify an exact expiration date')
    trade_parser.add_argument('-o', '--open-criteria', metavar='expr', nargs='*',
                              help='Specify one or more logical expressions '
                                   'that determine when the trade is opened.')
    trade_parser.add_argument('-c', '--close-criteria', metavar='expr', nargs='*',
                              help='Specify one or more logical expressions '
                                   'that determine when the trade is closed.')
    trade_parser.add_argument('-i', '--iv-rank', type=int, default=50,
                              help="Current IV "
                                   "ranking "
                                   "of stock")
    trade_parser.add_argument('-a', '--allocation', type=float, default=3,
                              help='Percentage of portfolio, '
                                   'in whole numbers, '
                                   'to put up for the trade')
    trade_parser.add_argument('-t', '--timeline', type=int, default=50,
                              help="Percentage of strategy's "
                                   "time range to target for "
                                   "expiry")
    trade_parser.add_argument('-s', '--days-out', type=int, default=0,
                              help='Number of days to target, '
                                   'cannot be used with timeline')
    trade_parser.add_argument('-w', '--spread-width', type=float, default=3,
                              help='Width of spreads')
    # Use const/default blank string to avoid ambiguity when retrieving from redis
    trade_parser.add_argument('-m', '--monthly', action='store_const', const='true',
                              help='Whether to only trade monthly contracts')
    parser.add_argument('-q', '--queue-name', required=True,
                        help='Redis queue name that the '
                             'daemon is reading from')

    args = parser.parse_args()
    trade_queue = TradeQueue(args.queue_name)
    args.func(args, trade_queue)


if __name__ == "__main__":
    cli()
