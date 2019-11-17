import subprocess
from datetime import datetime, time
from glob import glob
from os.path import join, dirname, basename

from math import erf, sqrt, log
from typing import List, Tuple, Dict

import pkg_resources
from pytz import timezone

from magictrade import storage


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


def send_trade(queue_name: str, args: Dict) -> str:
    identifier = "{}-{}".format(args['symbol'].upper(), datetime.now().strftime("%Y%m%d%H%M%S"))
    storage.hmset("{}:{}".format(queue_name, identifier), args)
    storage.lpush(queue_name, identifier)
    return identifier
