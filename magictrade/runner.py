import logging
import os
import random
from argparse import ArgumentParser
from typing import Dict

from time import sleep

from magictrade import storage
from magictrade.strategy.optionalpha import OptionAlphaTradingStrategy

from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.utils import market_is_open, get_version, get_allocation

parser = ArgumentParser()
parser.add_argument('-k', '--oauth-keyfile', dest='keyfile', help='Path to keyfile containing access and refresh '
                                                                  'tokens.')
parser.add_argument('-a', '--allocation', type=int, default=40, dest='allocation',
                    help='Percent of account to trade with.')
args = parser.parse_args()

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
broker = PaperMoneyBroker(balance=20_000, account_id="livetest",
                          username=os.environ.pop('username', None),
                          password=os.environ.pop('password', None),
                          mfa_code=os.environ.pop('mfa_code', None),
                          robinhood=True)
strategy = OptionAlphaTradingStrategy(broker)
queue_name = 'oatrading-queue'
rand_sleep = 3600, 7200


def normalize_trade(trade: Dict) -> Dict:
    trade['iv_rank'] = int(trade['iv_rank'])
    trade['allocation'] = float(trade['allocation'])
    trade['timeline'] = int(trade['timeline'])
    trade['days_out'] = int(trade['days_out'])
    trade['spread_width'] = float(trade['spread_width'])


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


def main_loop():
    next_maintenance = 0
    next_balance_check = 0
    first_trade = True

    while True:
        if market_is_open():
            if first_trade:
                sleep(60)
                first_trade = False
            if not next_maintenance:
                logging.info("Running maintenance...")
                try:
                    results = strategy.maintenance()
                except Exception as e:
                    logging.error("Error while performing maintenance:: {}".format(e))
                    try:
                        import sentry_sdk
                        sentry_sdk.capture_exception(e)
                    except ImportError:
                        pass
                else:
                    logging.info("Completed {} tasks.".format(len(results)))
                next_maintenance = random.randint(*rand_sleep)
                logging.info("Next check in {}s".format(next_maintenance))
            if not next_balance_check and broker.buying_power < broker.balance * (100 - args.allocation) / 100:
                next_balance_check = random.randint(*rand_sleep)
                logging.info("Not enough buying power. Sleeping {}s.".format(next_balance_check))
            elif not next_balance_check:
                while storage.llen(queue_name) > 0:
                    identifier = storage.rpop(queue_name)
                    trade = storage.hgetall("{}:{}".format(queue_name, identifier))
                    logging.info("Ingested trade: " + str(trade))
                    normalize_trade(trade)
                    try:
                        strategy.make_trade(**trade)
                    except Exception as e:
                        logging.error("Error while making trade '{}': {}".format(trade, e))
                        storage.set("{}:status:{}".format(queue_name, identifier), 'fail')
                        try:
                            import sentry_sdk
                            sentry_sdk.capture_exception(e)
                        except ImportError:
                            pass
                    else:
                        logging.info("Completed transaction: " + str(trade))
                        storage.set("{}:status:{}".format(queue_name, identifier), 'placed')
                if next_maintenance:
                    next_maintenance -= 1
                if next_balance_check:
                    next_balance_check -= 1
        else:  # market not open
            if next_maintenance:
                next_maintenance = 0
            first_trade = True
        sleep(1)


if __name__ == '__main__':
    main()
