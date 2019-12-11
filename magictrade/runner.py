import datetime
import logging
import os
import random
from argparse import ArgumentParser, Namespace

from requests import HTTPError
from time import sleep
from typing import Dict

from magictrade import storage
from magictrade.broker import brokers, load_brokers
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.broker.robinhood import RobinhoodBroker
from magictrade.broker.td_ameritrade import TDAmeritradeBroker
from magictrade.strategy import strategies, load_strategies
from magictrade.trade_queue import TradeQueue
from magictrade.utils import market_is_open, get_version, normalize_trade, handle_error

RAND_SLEEP = 1800, 6400
DEFAULT_TIMEOUT = 1800

load_brokers()
load_strategies()


def handle_results(result: Dict, identifier: str, trade: Dict):
    trade_queue.set_status(identifier, result.get('status', 'unknown'))
    # check if status is deferred, add a counter back to the original trade that the main loop will check and decrement
    if result.get('status') == 'deferred':
        trade['timeout'] = result.get('timeout', DEFAULT_TIMEOUT)
        trade_queue.add(identifier, trade)


def run_maintenance() -> None:
    logging.info("Running maintenance...")
    try:
        results = strategy.maintenance()
    except Exception as e:
        logging.error("Error while performing maintenance: {}".format(e))
        handle_error(e, args.debug)
    else:
        logging.info("Completed {} tasks.".format(len(results)))


def check_balance() -> int:
    try:
        buying_power = broker.buying_power
        balance = broker.balance
    except Exception as e:
        logging.error("Error while getting balances: {}".format(e))
        handle_error(e, args.debug)
    current_allocation = trade_queue.get_allocation() or args.allocation
    if buying_power < balance * (100 - current_allocation) / 100:
        trade_queue.set_current_usage(buying_power, balance)
        next_balance_check = random.randint(*RAND_SLEEP)
        logging.info("Not enough buying power, {}/{}. Sleeping {}s.".format(
            buying_power, balance, next_balance_check))
        return next_balance_check


def make_trade(trade: Dict, identifier: str) -> Dict:
    try:
        return strategy.make_trade(**trade)
    except Exception as e:
        logging.error("Error while making trade '{}': {}".format(trade, e))
        trade_queue.add_failed(identifier, str(e))
        handle_error(e, args.debug)


def get_next_trade():
    while True:
        identifier, trade = trade_queue.pop()
        if 'timeout' in trade and int(trade['timeout']):
            trade['timeout'] = int(trade['timeout']) - 1
            trade_queue.stage_trade(identifier, trade)
            trade_queue.set_data(identifier, trade)
        elif 'target_date' in trade and datetime.datetime.fromtimestamp(
                float(trade['target_date'])) > datetime.datetime.now():
            trade_queue.stage_trade(identifier)
        else:
            break

    logging.info("Ingested trade: " + str(trade))
    normalize_trade(trade)
    return identifier, trade


def main_loop():
    next_maintenance = 0
    next_balance_check = 0
    next_heartbeat = 0
    first_trade = False

    while True:
        if not next_heartbeat:
            trade_queue.heartbeat()
            next_heartbeat = 60
        if market_is_open() or args.debug:
            if not args.debug and first_trade:
                logging.info("Sleeping to make sure market is open...")
                sleep(random.randint(min(58, args.market_open_delay), args.market_open_delay))
                first_trade = False
            if not next_maintenance:
                run_maintenance()
                next_maintenance = random.randint(*RAND_SLEEP)
                logging.info("Next check in {}s".format(next_maintenance))
            elif not next_balance_check or trade_queue.pop_new_allocation():
                while len(trade_queue):
                    next_balance_check = check_balance()
                    if next_balance_check:
                        break
                    trade_queue.delete_current_usage()

                    identifier, trade = get_next_trade(len(trade_queue))
                    result = make_trade(trade, identifier)
                    if result:
                        logging.info("Processed trade: " + str(trade))
                        handle_results(result, identifier, trade)
                trade_queue.staged_to_queue()
                if next_maintenance:
                    next_maintenance -= 1
                if next_balance_check:
                    next_balance_check -= 1
        else:  # market not open
            if next_maintenance:
                next_maintenance = 0
            first_trade = True
        sleep(1)
        next_heartbeat -= 1


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Daemon to make automated trades.")
    parser.add_argument('-k', '--oauth-keyfile', dest='keyfile', help='Path to keyfile containing access and refresh '
                                                                      'tokens.')
    parser.add_argument('-x', '--authenticate-only', action='store_true', dest='authonly',
                        help='Authenticate and exit. '
                             'Useful for automatically '
                             'updating expired tokens.')
    parser.add_argument('-d', '--debug', action='store_true', dest='debug',
                        help='Simulate trades even if market is closed. '
                             'Exceptions are re-raised.')
    parser.add_argument('-a', '--allocation', type=int, default=40, dest='allocation',
                        help='Percent of account to trade with.')
    parser.add_argument('-u', '--username', dest='username', help='Username for broker account. May also specify with '
                                                                  'environment variable.')
    parser.add_argument('-p', '--password', dest='password', help='Password for broker account. May also specify with '
                                                                  'environment variable.')
    parser.add_argument('-m', '--mfa-code', dest='mfa', help='MFA code for broker account. May also specify with '
                                                             'environment variable.')
    parser.add_argument('-s', '--market-open-delay', type=int, default=600, help='Max time in seconds to sleep after '
                                                                                 'market opens.')
    parser.add_argument('-q', '--queue-name', help='Queue name to store data in.')
    parser.add_argument('broker', choices=brokers.keys(), help='Broker to use.')
    parser.add_argument('strategy', choices=strategies.keys(), help='Strategy to use.')
    return parser.parse_args()


def main():
    logging.info("Magictrade daemon {} starting with queue name '{}'.".format(get_version(), queue_name))
    try:
        import sentry_sdk

        logging.info("Sentry support enabled")
        sentry_sdk.init("https://251af7f144544ad893c4cb87dfddf7fa@sentry.io/1458727")
    except ImportError:
        pass
    logging.info("Authenticated with account " + broker.account_id)
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("Got SIGINT, Exiting...")


def handle_error(e: Exception):
    try:
        if isinstance(e, HTTPError):
            with open("http_debug.log", "a") as f:
                text = str(e.response.text)
                logging.error(text)
                f.write(text + "\n")
        if args.debug:
            raise e
        import sentry_sdk
        sentry_sdk.capture_exception(e)
    except ImportError:
        pass


def main_loop():
    next_maintenance = 0
    next_balance_check = 0
    next_heartbeat = 0
    first_trade = False

    while True:
        if not next_heartbeat:
            storage.set(queue_name + ":heartbeat", datetime.datetime.now().timestamp())
            next_heartbeat = 60
        if market_is_open() or args.debug:
            if not args.debug and first_trade:
                logging.info("Sleeping to make sure market is open...")
                sleep(random.randint(min(58, args.market_open_delay), args.market_open_delay))
                first_trade = False
            if not next_maintenance:
                logging.info("Running maintenance...")
                try:
                    results = strategy.maintenance()
                except Exception as e:
                    logging.error("Error while performing maintenance: {}".format(e))
                    handle_error(e)
                else:
                    logging.info("Completed {} tasks.".format(len(results)))
                next_maintenance = random.randint(*RAND_SLEEP)
                logging.info("Next check in {}s".format(next_maintenance))
            elif not next_balance_check or storage.get(queue_name + ":new_allocation"):
                storage.delete(queue_name + ":new_allocation")
                while storage.llen(queue_name) > 0:
                    try:
                        buying_power = broker.buying_power
                        balance = broker.balance
                    except Exception as e:
                        logging.error("Error while getting balances: {}".format(e))
                        handle_error(e)
                    current_allocation = int(storage.get(queue_name + ":allocation") or 0) or args.allocation
                    if buying_power < balance * (100 - current_allocation) / 100:
                        storage.set(queue_name + ":current_usage", f"{buying_power}/{balance}")
                        next_balance_check = random.randint(*RAND_SLEEP)
                        logging.info("Not enough buying power, {}/{}. Sleeping {}s.".format(
                            buying_power, balance, next_balance_check))
                        break
                    storage.delete(queue_name + ":current_usage")
                    identifier = storage.rpop(queue_name)
                    trade = storage.hgetall("{}:{}".format(queue_name, identifier))
                    logging.info("Ingested trade: " + str(trade))
                    normalize_trade(trade)

                    try:
                        result = strategy.make_trade(**trade)
                    except Exception as e:
                        logging.error("Error while making trade '{}': {}".format(trade, e))
                        storage.lpush(queue_name + "-failed", identifier)
                        storage.set("{}:status:{}".format(queue_name, identifier), str(e))
                        handle_error(e)
                    else:
                        logging.info("Completed transaction: " + str(trade))
                        handle_results(result, identifier, trade)
                if next_maintenance:
                    next_maintenance -= 1
                if next_balance_check:
                    next_balance_check -= 1
        else:  # market not open
            if next_maintenance:
                next_maintenance = 0
            first_trade = True
        sleep(1)
        next_heartbeat -= 1


if __name__ == '__main__':
    args = parse_args()

    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
    if 'username' in os.environ:
        logging.info("Attempting credentials from envars...")
    elif args.username:
        logging.info("Attempting credentials from args...")
    else:
        logging.info("Using stored credentials...")
        if not os.path.exists(args.keyfile):
            logging.error("Can't find keyfile. Aborting.")
            raise SystemExit
    username = os.environ.pop('username', None) or args.username
    password = os.environ.pop('password', None) or args.password
    mfa_code = os.environ.pop('mfa_code', None) or args.mfa

    broker_kwargs = {}
    if args.broker == 'papermoney':
        broker = PaperMoneyBroker(balance=15_000, account_id="livetest",
                                  username=username,
                                  password=password,
                                  mfa_code=mfa_code,
                                  robinhood=True, token_file=args.keyfile)
    elif args.broker == 'robinhood':
        broker = RobinhoodBroker(username=username, password=password,
                                 mfa_code=mfa_code, token_file=args.keyfile)
    elif args.broker == 'tdameritrade':
        broker = TDAmeritradeBroker(account_id=args.username)
    else:
        logging.warning("No valid broker provided. Exiting...")
        raise SystemExit
    if args.authonly:
        logging.info("Authentication success. Exiting.")
        raise SystemExit
    queue_name = args.queue_name
    if not queue_name:
        raise SystemExit("Must provide queue name.")
    trade_queue = TradeQueue(queue_name)
    strategy = strategies[args.strategy](broker)
