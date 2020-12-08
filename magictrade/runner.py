import datetime
import logging
import os
import random
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from typing import Dict, Tuple

from requests import HTTPError
from time import sleep

from magictrade.broker import brokers, load_brokers, Broker
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.broker.robinhood import RobinhoodBroker
from magictrade.broker.td_ameritrade import TDAmeritradeBroker
from magictrade.strategy import strategies, load_strategies, TradingStrategy, NoTradeException
from magictrade.trade_queue import RedisTradeQueue
from magictrade.utils import market_is_open, get_version, normalize_trade, handle_error

DEFAULT_MAINTENANCE_SLEEP = 900, 1800
DEFAULT_TIMEOUT = 1800

load_brokers()
load_strategies()


class Runner:
    def __init__(self, args: Namespace, trade_queue: RedisTradeQueue, broker: Broker,
                 enabled_strategies: TradingStrategy, maintenance_sleep: Tuple[int, int] = DEFAULT_MAINTENANCE_SLEEP):
        self.args = args
        self.trade_queue = trade_queue
        self.broker = broker
        self.strategies = enabled_strategies
        self.maintenance_sleep = maintenance_sleep

    def handle_results(self, result: Dict, identifier: str, trade: Dict):
        self.trade_queue.set_status(identifier, result.get('status', 'unknown'))
        # check if status is deferred, add a target time back to the original trade that the main loop will check and
        if result.get('status') == 'deferred':
            timeout = int(result.get('timeout', DEFAULT_TIMEOUT))
            trade['start'] = result.get('start', self.broker.date.timestamp() + timeout)
            self.trade_queue.add(identifier, trade)
        elif result.get('status') == 'rejected':
            self.trade_queue.add_failed(identifier, result.get('msg'))

    def run_maintenance(self) -> None:
        logging.info("Running maintenance...")
        for strategy in self.strategies:
            try:
                results = strategy.maintenance()
            except Exception as e:
                logging.error("Error while performing maintenance: {}".format(e))
                strategy.log("Fatal error while performing maintenance: {}.".format(e))
                handle_error(e, self.args.debug)
            else:
                logging.info("Completed {} tasks.".format(len(results)))
        self.trade_queue.last_maintenance = self.broker.date

    def check_balance(self) -> int:
        next_balance_check = random.randint(*self.maintenance_sleep)
        try:
            buying_power = self.broker.buying_power
            balance = self.broker.balance
        except Exception as e:
            logging.error("Error while getting balances: {}, sleeping {}s".format(
                e, next_balance_check))
            handle_error(e, self.args.debug)
            return next_balance_check
        current_allocation = self.trade_queue.get_allocation() or self.args.allocation
        if buying_power < balance * (100 - current_allocation) / 100:
            self.trade_queue.set_current_usage(buying_power, balance)
            logging.info("Not enough buying power, {}/{}. Sleeping {}s.".format(
                buying_power, balance, next_balance_check))
            return next_balance_check

    def make_trade(self, trade: Dict, identifier: str) -> Dict:
        if strategy := trade.pop('strategy', None):
            try:
                strategy = next(s for s in self.strategies if s.name == strategy)
            except StopIteration:
                raise Exception(f"Invalid strategy {strategy} specified.")
        else:
            strategy = self.strategies[0]
        try:
            return strategy.make_trade(**trade)
        except Exception as e:
            if isinstance(e, HTTPError):
                # pylint: disable=no-member
                result = e.response.text
            elif isinstance(e, NoTradeException):
                logging.warning("Non-application error while making trade '{}': {}".format(trade, e))
                return
            else:
                result = str(e)
            strategy.log(f"Fatal error making trade in '{trade['symbol']}': {str(e)}.")
            logging.error("Error while making trade '{}': {}".format(trade, e))
            self.trade_queue.add_failed(identifier, result)
            handle_error(e, self.args.debug)

    def check_trade_expired(self, trade: Dict) -> bool:
        return 'end' in trade and datetime.datetime.fromtimestamp(
            float(trade['end'])) <= self.broker.date

    def get_next_trade(self, clean_only: bool = False) -> (str, Dict):
        while len(self.trade_queue):
            identifier, trade = self.trade_queue.pop()
            if self.check_trade_expired(trade):
                # Trade not re-added to queue since it is expired
                continue
            elif 'start' in trade and datetime.datetime.fromtimestamp(
                    float(trade['start'])) > self.broker.date:
                self.trade_queue.stage_trade(identifier)
            else:
                if clean_only:
                    self.trade_queue.stage_trade(identifier)
                    continue
                # Clean up these keys since they aren't used later on
                for key in ('start', 'end'):
                    trade.pop(key, None)
                logging.info("Ingested trade: " + str(trade))
                normalize_trade(trade)
                trade['open_criteria'], trade['close_criteria'], trade[
                    'trade_criteria'] = self.trade_queue.get_criteria(identifier)
                return identifier, trade
        return None, None

    def run(self):
        next_maintenance = 0
        next_balance_check = 0
        next_heartbeat = 0
        first_trade = False
        cleanup_ran = False

        while True:
            try:
                if not next_heartbeat:
                    self.trade_queue.heartbeat()
                    next_heartbeat = 15
                if market_is_open() or self.args.debug:
                    if not self.args.debug and first_trade:
                        logging.info("Sleeping to make sure market is open...")
                        sleep(random.randint(min(58, self.args.market_open_delay),
                                             self.args.market_open_delay))
                        first_trade = False
                    if not next_maintenance or self.trade_queue.should_run_maintenance():
                        self.run_maintenance()
                        next_maintenance = random.randint(*self.maintenance_sleep)
                        logging.info("Next check in {}s".format(next_maintenance))
                    elif not next_balance_check or self.trade_queue.pop_new_allocation():
                        while len(self.trade_queue):
                            next_balance_check = self.check_balance()
                            if next_balance_check:
                                break
                            self.trade_queue.delete_current_usage()

                            identifier, trade = self.get_next_trade()
                            if trade:
                                result = self.make_trade(trade, identifier)
                                if result:
                                    logging.info("Processed trade: " + str(trade))
                                    self.handle_results(result, identifier, trade)
                        self.trade_queue.staged_to_queue()
                        if next_maintenance:
                            next_maintenance -= 1
                        if next_balance_check:
                            next_balance_check -= 1
                    cleanup_ran = False
                else:  # market not open
                    if next_maintenance:
                        next_maintenance = 0
                    if not cleanup_ran:
                        cleanup_ran = True
                        self.get_next_trade(clean_only=True)
                        self.trade_queue.staged_to_queue()
                    first_trade = True
                sleep(1)
                next_heartbeat -= 1
            except Exception as e:
                # Catch-all exception handler
                handle_error(e, self.args.debug)


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Daemon to make automated trades.",
                            formatter_class=ArgumentDefaultsHelpFormatter)
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
    parser.add_argument('-r', '--paper', action='store_true',
                        help='Whether to do paper trading instead of real trades.')
    parser.add_argument('-u', '--username', dest='username', help='Username for broker account. May also specify with '
                                                                  'environment variable.')
    parser.add_argument('-p', '--password', dest='password', help='Password for broker account. May also specify with '
                                                                  'environment variable.')
    parser.add_argument('-m', '--mfa-code', dest='mfa', help='MFA code for broker account. May also specify with '
                                                             'environment variable.')
    parser.add_argument('-s', '--market-open-delay', type=int, default=600, help='Max time in seconds to sleep after '
                                                                                 'market opens.')
    parser.add_argument('-q', '--queue-name', help='Queue name to store data in.')
    parser.add_argument('-t', '--maintenance-timeout', type=int, nargs=2, metavar=('lower_bound', 'upper_bound'),
                        default=DEFAULT_MAINTENANCE_SLEEP,
                        help='A range for the amount of time to wait between maintenance checks, '
                             'in seconds. The actual timeout will be randomly chosen from this range.')
    parser.add_argument('broker', choices=brokers.keys(), help='Broker to use.')
    parser.add_argument('strategies', metavar='strategy', choices=strategies.keys(), nargs="+",
                        help='Strategies to use. The first one will '
                             'be the default for any untagged '
                             'trades.')
    return parser.parse_args()


def main():
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

    if args.broker == 'robinhood':
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
    if args.paper:
        broker = PaperMoneyBroker(broker=broker)
    queue_name = args.queue_name
    if not queue_name:
        raise SystemExit("Must provide queue name.")
    trade_queue = RedisTradeQueue(queue_name)
    enabled_strategies = []
    for strategy in args.strategies:
        enabled_strategies.append(strategies[strategy](broker, args.paper))
    logging.info("Magictrade daemon {} starting with queue name '{}'.".format(get_version(), queue_name))
    try:
        import sentry_sdk

        logging.info("Sentry support enabled")
        sentry_sdk.init("https://251af7f144544ad893c4cb87dfddf7fa@sentry.io/1458727")
    except ImportError:
        pass
    logging.info("Authenticated with account " + broker.account_id)
    runner = Runner(args, trade_queue, broker, enabled_strategies)
    try:
        runner.run()
    except KeyboardInterrupt:
        logging.info("Got SIGINT, Exiting...")


if __name__ == '__main__':
    main()
