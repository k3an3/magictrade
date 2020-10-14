import datetime
import random
from time import sleep

import sys


def init_script(args, name) -> None:
    """
    Some functionality commonly needed in scripts.
    :param args: argparse Namespace from CLI.
    :param name: Name of this runner.
    :return:
    """
    print(f"Starting {name} runner at",
          datetime.datetime.now().isoformat())
    if args.run_probability:
        if random.randint(0, 100) > args.run_probability:
            print("Randomly deciding to not trade today.")
            sys.exit(0)
    if args.random_sleep:
        seconds = random.randint(*args.random_sleep)
        print(f"Sleeping for {seconds}s.")
        sleep(seconds)
