#!/usr/bin/env python3
import os
from argparse import ArgumentParser
from datetime import datetime, timedelta
from pprint import pprint

import requests
from bs4 import BeautifulSoup

from magictrade.trade_queue import TradeQueue
from magictrade.utils import get_all_trades

COOKIE_NAME = 'wordpress_logged_in_0e339d0792c43f894b0e59fcb8d3fb24'
EARNINGS_DAYS_EXP = 3
EARNINGS_ALLOCATION = 3
EARNINGS_IV = 52
DEFAULT_ALLOCATION = 3
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:68.0) Gecko/20100101 Firefox/68.0',

}
MINUTES_BEFORE_CLOSE = 45
URL = 'https://optionalpha.com/'

trade_time = {
    'Before Open': timedelta(hours=-8, minutes=-1 * MINUTES_BEFORE_CLOSE),
    'After Close': timedelta(hours=15, minutes=60 - MINUTES_BEFORE_CLOSE),
}


def request(url: str, cookie: str):
    r = requests.get(URL + url, cookies={COOKIE_NAME: cookie},
                     headers=HEADERS)
    r.raise_for_status()
    return r


def earnings_process_day(day):
    date = datetime.strptime(day.h3.text.split()[1], '%m/%d/%Y')
    earnings = []
    for stock in day.find_all(class_='earning-stock'):
        try:
            earnings.append({
                'start': (date + trade_time[stock.h4.text]).timestamp(),
                'end': (date + trade_time[stock.h4.text] + timedelta(minutes=MINUTES_BEFORE_CLOSE)).timestamp(),
                'symbol': stock.h3.text,
                'monthly': False,
                'iv_rank': EARNINGS_IV,
                'allocation': EARNINGS_ALLOCATION,
                'days_out': EARNINGS_DAYS_EXP,
                'direction': 'neutral',
            })
        except KeyError:
            print(f"Earnings time '{stock.h4.text}' not valid, skipping...")
    return earnings


def fetch_earnings(cookie):
    r = request('members/earnings-calendar', cookie)
    soup = BeautifulSoup(r.text, features="html.parser")
    earnings = []
    for day in soup.find_all(class_='day'):
        if day_earnings := earnings_process_day(day):
            earnings.extend(day_earnings)
    return earnings


def watchlist_process_stock(stock):
    if stock.find(class_='earningcornercontainer'):
        return
    return {
        'symbol': stock.h1.text,
        'iv_rank': int(stock.find(class_='bar-percentage').text.split()[2]),
        'monthly': True,
        'allocation': DEFAULT_ALLOCATION,
        'direction': 'neutral',
        'end': datetime.now().replace(hour=16, minute=0, second=0, microsecond=0).timestamp()
    }


def fetch_watchlist(cookie):
    r = request('members/watch-list', cookie)
    soup = BeautifulSoup(r.text, features="html.parser")
    trades = []
    for stock in soup.find_all(class_='oagrid-item highiv'):
        if trade := watchlist_process_stock(stock):
            trades.append(trade)
    return trades


def main(args):
    if args.cookie:
        cookie = args.cookie
    else:
        try:
            cookie = os.environ['COOKIE']
        except KeyError:
            print("Error: Must specify cookie value in argument or environment variable!")
            raise SystemExit
    if args.trade and not args.trade_queue:
        print("Error: --trade-queue is required with --trade!!")
        raise SystemExit
    if args.trade:
        tq = TradeQueue(args.trade_queue)
    positions = set()
    try:
        if args.account_id:
            positions = set([t['data']['symbol'] for t in get_all_trades(args.account_id)])
    except AttributeError:
        pass
    for n, trade in enumerate(args.func(cookie)):
        if args.trade:
            if trade['symbol'] not in positions:
                tq.send_trade(trade)
        else:
            pprint(trade)
    if args.trade:
        print("Placed", n + 1, "trades.")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-c', '--cookie', help="{COOKIE_NAME} cookie value for optionalpha.com")
    parser.add_argument('-q', '--trade-queue', required=False, help="Name of the magictrade queue to add trades to")
    subparsers = parser.add_subparsers(dest='cmd', help='Valid subcommands:', required=True)
    earnings_parser = subparsers.add_parser('earnings')
    earnings_parser.set_defaults(func=fetch_earnings)
    earnings_parser.add_argument('-t', '--trade', help='Place trades from received data instead of just printing out.')
    watchlist_parser = subparsers.add_parser('watchlist')
    watchlist_parser.set_defaults(func=fetch_watchlist)
    watchlist_parser.add_argument('-t', '--trade', help='Place trades from received data instead of just printing out.')
    watchlist_parser.add_argument('-a', '--account-id', help='If set, will check existing trades to avoid securities '
                                                             'with active trades.')
    main(parser.parse_args())