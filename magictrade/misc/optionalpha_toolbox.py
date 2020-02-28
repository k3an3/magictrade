#!/usr/bin/env python3
import os
import random
from pprint import pprint

import requests
import shutil
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime, timedelta

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("This module requires BeautifulSoup4.")
try:
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
except ImportError:
    raise SystemExit("This module requires selenium.")
from time import sleep

from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import get_all_trades

COOKIE_NAME = 'wordpress_logged_in_0e339d0792c43f894b0e59fcb8d3fb24'
COOKIE_FILE = '.oa-cookie'
EARNINGS_DAYS_EXP = 3
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


def earnings_process_day(day, allocation):
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
                'allocation': allocation,
                'days_out': EARNINGS_DAYS_EXP,
                'direction': 'neutral',
            })
        except KeyError:
            print(f"Earnings time '{stock.h4.text}' not valid, skipping...")
    return earnings


def authenticate(username: str, password: str) -> str:
    options = Options()
    options.add_argument('-headless')
    browser = webdriver.Firefox(options=options)
    browser.get('https://optionalpha.com/')
    if 'Options' not in browser.title:
        browser.quit()
        raise SystemExit("Can't reach OptionAlpha.")

    sleep(random.randint(121, 2347) * .01)
    browser.find_element_by_css_selector(".fa-sign-in").click()
    sleep(random.randint(606, 1209) * .01)
    browser.find_element_by_id('log').send_keys(username)
    sleep(random.randint(140, 420) * .01)
    browser.find_element_by_id('pwd').send_keys(password)
    sleep(random.randint(45, 399) * .01)
    browser.find_element_by_id('mm-login-button').click()
    sleep(10)
    if not browser.current_url == 'https://optionalpha.com/members':
        browser.quit()
        raise SystemExit("Invalid credentials.")
    cookie = browser.get_cookie(COOKIE_NAME)['value']
    browser.quit()
    return cookie


# noinspection PyUnusedLocal
def fetch_earnings(cookie, args):
    r = request('members/earnings-calendar', cookie)
    soup = BeautifulSoup(r.text, features="html.parser")
    earnings = []
    for day in soup.find_all(class_='day'):
        if day_earnings := earnings_process_day(day, args.allocation):
            earnings.extend(day_earnings)
    return earnings


def watchlist_process_stock(stock, allocation):
    if stock.find(class_='earningcornercontainer'):
        # Don't place if earnings coming up.
        return
    return {
        'symbol': stock.h1.text,
        'iv_rank': int(stock.find(class_='bar-percentage').text.split()[2]),
        'monthly': True,
        'allocation': allocation,
        'direction': 'neutral',
        'end': datetime.now().replace(hour=16, minute=0, second=0, microsecond=0).timestamp()
    }


def fetch_watchlist(cookie, args):
    r = request('members/watch-list', cookie)
    soup = BeautifulSoup(r.text, features="html.parser")
    trades = []
    for stock in soup.find_all(class_='oagrid-item highiv'):
        if trade := watchlist_process_stock(stock, args.allocation):
            trades.append(trade)
    return trades


def main(args):
    if not (shutil.which("geckodriver") and shutil.which('firefox')):
        raise SystemExit("'geckodriver' and 'firefox' must be installed and in PATH.")
    username = os.environ.get('LOGIN')
    password = os.environ.get('PASSWORD')
    if not (username and password):
        raise SystemExit("Must provide LOGIN and PASSWORD environment variables.")
    if args.random_sleep:
        seconds = random.randint(*args.random_sleep)
        print(f"Sleeping for {seconds}s.")
        sleep(seconds)
    if os.path.isfile(COOKIE_FILE):
        print("Using saved cookie.")
        with open(COOKIE_FILE) as f:
            cookie = f.read()
    else:
        print(f"Using credentials for '{username}'.")
        cookie = authenticate(username, password)
        print("Successful authentication with credentials.")
        with open(COOKIE_FILE, 'w') as f:
            f.write(cookie)

    if args.trade and not args.trade_queue:
        raise SystemExit("Error: --trade-queue is required with --trade!!")
    if request('members', cookie).url == 'https://optionalpha.com/member-login':
        print("Cookie expired, re-authenticating.")
        cookie = authenticate(username, password)
        with open(COOKIE_FILE, 'w') as f:
            f.write(cookie)
    positions = set()
    try:
        if args.account_id:
            positions = set([t['data']['symbol'] for t in get_all_trades(args.account_id)])
    except AttributeError:
        pass
    if args.trade:
        tq = RedisTradeQueue(args.trade_queue)
        positions |= set([tq.get_data(t)['symbol'] for t in tq])
    for n, trade in enumerate(args.func(cookie, args)):
        if args.trade_count and n + 1 > args.trade_count:
            break
        if args.trade:
            if trade['symbol'] not in positions:
                tq.send_trade(trade)
        else:
            pprint(trade)
    if args.trade:
        print("Placed", n + 1, "trades.")


def cli():
    parser = ArgumentParser(description="OptionAlpha toolbox integration for magictrade.",
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-q', '--trade-queue', help="Name of the magictrade queue to add trades to.")
    parser.add_argument('-c', '--trade-count', type=int, help="Max number of trades to place.")
    parser.add_argument('-l', '--allocation', type=int, default=DEFAULT_ALLOCATION, help="Name of the magictrade "
                                                                                         "queue to add trades to.")
    parser.add_argument('-r', '--random-sleep', type=int, nargs=2, metavar=('min', 'max'),
                        help="Range of seconds to randomly sleep before running.")
    subparsers = parser.add_subparsers(dest='cmd', help='Valid subcommands:', required=True)
    earnings_parser = subparsers.add_parser('earnings')
    earnings_parser.set_defaults(func=fetch_earnings)
    earnings_parser.add_argument('-t', '--trade', action='store_true', help='Place trades from received data instead '
                                                                            'of just printing out.')
    watchlist_parser = subparsers.add_parser('watchlist')
    watchlist_parser.set_defaults(func=fetch_watchlist)
    watchlist_parser.add_argument('-t', '--trade', action='store_true', help='Place trades from received data instead '
                                                                             'of just printing out.')
    watchlist_parser.add_argument('-a', '--account-id', help='If set, will check existing trades to avoid securities '
                                                             'with active trades.')
    main(parser.parse_args())


if __name__ == "__main__":
    cli()
