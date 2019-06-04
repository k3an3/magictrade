import argparse
import subprocess
from datetime import datetime, time
from typing import List, Tuple, Dict

import matplotlib.pyplot as plt
import pkg_resources
from matplotlib import rcParamsDefault, rcParams, pyplot
from pytz import timezone

from magictrade import storage


def plot_cli():
    parser = argparse.ArgumentParser(description='Plot results of trading algorithms.')
    parser.add_argument('account_ids', metavar='id', nargs='+',
                        help='Display graphs for these account IDs in the database.')
    parser.add_argument('-t', '--ticks', dest='ticks', type=int, default=30,
                        help='How many ticks to display on the x-axis.')
    args = parser.parse_args()
    plot_account_balances(args.account_ids, args.ticks)


# Shamelessly ripped from https://github.com/WillKoehrsen/Data-Analysis/blob/master/stocker/stocker.py; MIT licensed

def reset_plot():
    # Restore default parameters
    rcParams.update(rcParamsDefault)

    # Adjust a few parameters to liking
    rcParams['figure.figsize'] = (20, 10)
    rcParams['axes.labelsize'] = 10
    rcParams['xtick.labelsize'] = 8
    rcParams['ytick.labelsize'] = 8
    rcParams['axes.titlesize'] = 14
    rcParams['text.color'] = 'k'


def get_account_history(account_id: str) -> Tuple[List[str], List[float]]:
    return storage.lrange(account_id + ":dates", 0, -1), \
           [float(v) for v in storage.lrange(account_id + ":values", 0, -1)]


def plot_account_balances(account_ids: List[str], graph_ticks: int = 30, trades: Dict = {}) -> None:
    reset_plot()

    colors = ['b', 'c', 'm', 'k']

    for i, dv in enumerate([get_account_history(a) for a in account_ids]):
        plt.figure("Magictrade")
        plt.style.use('fivethirtyeight')
        plt.plot(dv[0], dv[1], color=colors[i], linewidth=3, label=account_ids[i], alpha=0.8)
        plt.xlabel('Date')
        plt.xticks(dv[0], rotation='vertical')
        plt.ylabel('USD')
        pyplot.locator_params(axis='x', nbins=graph_ticks)
        try:
            plt.title('Strategy Comparison {} to {}'.format(dv[0][0], dv[0][-1]))
        except IndexError:
            print("Warning: there was no data for account '{}'. Skipping...".format(account_ids[i]))
            continue
        plt.legend(prop={'size': 10})
        plt.grid(color='k', alpha=0.4)
        buy_plot = ([], [])
        sell_plot = ([], [])
        for j, k in enumerate(dv[0]):
            t = trades.get(k)
            if t:
                if t[0] == 'buy':
                    buy_plot[0].append(k)
                    buy_plot[1].append(dv[1][j])
                elif t[0] == 'sell':
                    sell_plot[0].append(k)
                    sell_plot[1].append(dv[1][j])
        if buy_plot[0]:
            plt.plot(buy_plot[0], buy_plot[1], linestyle='None', marker='^', color='g', markersize=12)
        if sell_plot[0]:
            plt.plot(sell_plot[0], sell_plot[1], linestyle='None', marker='v', color='r', markersize=12)

    plt.show()


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


if __name__ == "__main__":
    plot_cli()
