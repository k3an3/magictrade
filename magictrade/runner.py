import logging
import random

from time import sleep

from magictrade import storage
from magictrade.strategy.optionalpha import OptionAlphaTradingStrategy

from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.utils import market_is_open, get_version

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
broker = PaperMoneyBroker(balance=20_000, account_id="livetest")
strategy = OptionAlphaTradingStrategy(broker)
queue_name = 'oatrading-queue'
rand_sleep = 3600, 7200
next_run = 0
logging.info("Magictrade daemon {} starting with queue name '{}'.".format(get_version(), queue_name))

while True:
    if True or market_is_open():
        if not next_run:
            logging.info("Running maintenance...")
            logging.info("Completed {} tasks.".format(len(strategy.maintenance())))
            next_run = random.randint(*rand_sleep)
            logging.info("Next check in {}s".format(next_run))
        while storage.llen(queue_name) > 0:
            identifier = storage.rpop(queue_name)
            trade = storage.hgetall("{}:{}".format(queue_name, identifier))
            logging.info("Ingested trade: " + str(trade))
            strategy.make_trade(**trade)
        if next_run:
            next_run -= 1
    else:
        if next_run:
            next_run = 0
    sleep(1)
