import calendar
import logging
import subprocess
from ast import literal_eval
from datetime import datetime, time, timedelta
from glob import glob
from os.path import join, dirname, basename
from typing import List, Tuple, Dict, Callable

import pkg_resources
from math import erf, sqrt, log
from pytz import timezone
from redis import StrictRedis
from requests import HTTPError

from magictrade import storage, Broker
from magictrade.securities import Option


def safe_abs(x, /):
    try:
        return abs(x)
    except TypeError:
        return 0


def import_modules(base_path: str, parent_module: str) -> None:
    for x in glob(join(dirname(base_path), '*.py')):
        if not basename(x).startswith('__'):
            __import__(f'magictrade.{parent_module}.{basename(x)[:-3]}', globals(), locals())


def calculate_percent_otm(current_price: float, strike_price: float, iv: float, days_to_exp: int):
    cnd = lambda x: (1.0 + erf(x / sqrt(2.0))) / 2.0
    result = cnd(log(strike_price / current_price) / (iv / 100 * sqrt(days_to_exp / 365)))
    if strike_price < current_price:
        return round(1 - result, 2)
    return round(result, 2)


def get_account_history(account_id: str) -> Tuple[List[str], List[float]]:
    return storage.lrange(account_id + ":dates", 0, -1), \
           [float(v) for v in storage.lrange(account_id + ":values", 0, -1)]


def get_percentage_change(start: float, end: float) -> float:
    chg = end - start
    return chg / start * 100


def get_price_from_change(start: float, change: float) -> float:
    chg = (start * change / 100)
    return start + chg


def market_is_open() -> bool:
    market_open = time(9, 30)
    market_close = time(16, 00)
    eastern = datetime.now(timezone('US/Eastern'))
    return eastern.isoweekday() not in (6, 7) and market_open <= eastern.time() < market_close


def get_version():
    try:
        return 'v' + pkg_resources.require("magictrade")[0].version
    except pkg_resources.DistributionNotFound:
        try:
            ver = 'v' + subprocess.run(['git', 'describe', '--tags', 'HEAD'],
                                       capture_output=True).stdout.decode('UTF-8')
            if ver == 'v':
                return 'dev-' + subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True).stdout.decode(
                    'UTF-8')[:7]
            return ver
        except:
            return 'v?'


def get_allocation(broker, allocation: int):
    return broker.balance * allocation / 100


def generate_identifier(symbol: str) -> str:
    return "{}-{}".format(symbol.upper(), datetime.now().strftime("%Y%m%d%H%M%S"))


def date_format(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def from_date_format(date: str) -> str:
    return datetime.strptime(date, "%Y-%m-%d")


def get_monthly_option(start_date: datetime = None) -> str:
    month = start_date.month
    first_day_of_month = datetime(start_date.year, month, 1)
    first_friday = first_day_of_month + timedelta(
        days=((4 - calendar.monthrange(start_date.year, month)[0]) + 7) % 7)
    return date_format(first_friday + timedelta(days=14))


def get_risk(spread_width: float, price: float) -> float:
    return (spread_width - price) * 100


def normalize_trade(trade: Dict) -> Dict:
    funcs = {
        'iv_rank': int,
        'allocation': float,
        'timeline': int,
        'days_out': int,
        'spread_width': float,
    }
    # Copy to list so dict isn't modified during iteration
    for key, value in list(trade.items()):
        if value and key in funcs:
            trade[key] = funcs[key](value)
        elif not value:
            del trade[key]


def handle_error(e: Exception, debug: bool = False):
    try:
        if isinstance(e, HTTPError):
            with open("http_debug.log", "a") as f:
                text = str(e.response.text)
                logging.error(text)
                f.write(text + "\n")
        if debug:
            raise e
        import sentry_sdk
        sentry_sdk.capture_exception(e)
    except ImportError:
        pass


def get_offset_date(broker: Broker, days: int) -> str:
    return (broker.date + timedelta(days=days)).strftime("%Y-%m-%d")


def get_all_trades(account_name: str, position_storage: StrictRedis = None):
    """
    Given an account name, return all positions that are currently open. Function name seems to be a misnomer.
    :param account_name: Name of the account to fetch positions for.
    :param position_storage: If the redis host is not localhost, pass an externally-created Redis instance here.
    :return: A list of trades in dict format.
    """
    position_storage = position_storage or storage
    positions = position_storage.lrange(account_name + ":positions", 0, -1)
    trades = []
    if positions:
        for p in positions:
            try:
                raw = literal_eval(position_storage.get("{}:raw:{}".format(account_name, p)))
            except ValueError:
                raw = []
            trades.append({'instrument': raw,
                           'data': position_storage.hgetall('{}:{}'.format(account_name, p))})
    return trades


def find_option_with_probability(options: List, probability: int, max_probability: int = 100):
    for option in sorted(options, key=lambda o: o.probability_otm):
        if probability <= option.probability_otm * 100 < max_probability:
            return option


def find_option_with(options: List[Option], func: Callable, key: Callable, reverse: bool = False):
    for option in sorted(options, key=key, reverse=reverse):
        if func(option):
            return option


def generate_trade_alert(action: str, quantity: int, trade_type: str, symbol: str, exp_date: str,
                         legs: List[Dict], credit: float) -> str:
    if action == 'sell':
        action = 'SOLD'
        quantity *= -1
    else:
        action = 'BOT'
    if trade_type == 'credit_spread':
        side = legs[0][0].option_type
    trade_type = {'credit_spread': 'CREDIT SPREAD',
                  'iron_condor': 'IRON CONDOR',
                  'iron_butterfly': 'IRON BUTTERFLY'}[trade_type]
    strikes = '/'.join([f"{'-' if side == 'sell' else ''}{leg.strike_price}" for leg, side in legs])
    return ' '.join((action, quantity, trade_type, symbol, exp_date, strikes, side, credit)).upper().replace('  ', ' ')


def bool_as_str(b: bool) -> str:
    return 'true' if b else ''
