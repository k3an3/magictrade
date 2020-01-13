#!/usr/bin/env python3
import os
from argparse import ArgumentParser
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from magictrade.trade_queue import TradeQueue

COOKIE_NAME = 'wordpress_logged_in_0e339d0792c43f894b0e59fcb8d3fb24'
DAYS_EXP = 3
ALLOCATION = 3
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:68.0) Gecko/20100101 Firefox/68.0',

}

trade_time = {
    'Before Open': timedelta(hours=-8, minutes=-30),
    'After Close': timedelta(hours=15, minutes=30),
}


def process_day(day):
    date = datetime.strptime(day.h3.text.split()[1], '%m/%d/%Y')
    earnings = []
    for stock in day.find_all(class_='earning-stock'):
        try:
            earnings.append({
                'date': date + trade_time[stock.h4.text],
                'symbol': stock.h3.text
            })
        except KeyError:
            print(f"Earnings time '{stock.h4.text}' not valid, skipping...")
    return earnings


def fetch_earnings(cookie):
    r = requests.get('https://optionalpha.com/members/earnings-calendar', cookies={COOKIE_NAME: cookie},
                     headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, features="html.parser")
    earnings = []
    for day in soup.find_all(class_='day'):
        if day_earnings := process_day(day):
            earnings.extend(day_earnings)
    return earnings


def main(args):
    if args.cookie:
        cookie = args.cookie
    else:
        try:
            cookie = os.environ['COOKIE']
        except KeyError:
            print("Error: Must specify cookie value in argument or environment variable!")
            raise SystemExit
    tq = TradeQueue(args.trade_queue)
    for n, earning in enumerate(fetch_earnings(cookie)):
        tq.send_trade({
            'symbol': earning['symbol'],
            'days_out': DAYS_EXP,
            'direction': 'neutral',
            'iv_rank': 100,
            'monthly': False,
            'allocation': ALLOCATION,
            'open_criteria': [{'expr': f'date >= {earning["date"].timestamp()}'}],
        })
    print("Placed", n + 1, "trades.")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-c', '--cookie', help="{COOKIE_NAME} cookie value for optionalpha.com")
    parser.add_argument('-q', '--trade-queue', required=True, help="Name of the magictrade queue to add trades to")
    main(parser.parse_args())
