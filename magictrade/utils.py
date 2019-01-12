import random
from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib import rcParamsDefault, rcParams

from magictrade import storage


def plot_cli():
    plot_account_balances(['test'])


# Shamelessly ripped from https://github.com/WillKoehrsen/Data-Analysis/blob/master/stocker/stocker.py; MIT licensed

def reset_plot():
    # Restore default parameters
    rcParams.update(rcParamsDefault)

    # Adjust a few parameters to liking
    rcParams['figure.figsize'] = (8, 5)
    rcParams['axes.labelsize'] = 10
    rcParams['xtick.labelsize'] = 8
    rcParams['ytick.labelsize'] = 8
    rcParams['axes.titlesize'] = 14
    rcParams['text.color'] = 'k'


def get_account_history(account_id: str) -> Tuple[List[str], List[float]]:
    return storage.lrange(account_id + ":dates", 0, -1), \
           [float(v) for v in storage.lrange(account_id + ":values", 0, -1)]


def plot_account_balances(account_ids: List[str]) -> None:
    reset_plot()

    colors = ['r', 'b', 'g', 'y', 'c', 'm']

    for i, dv in enumerate([get_account_history(a) for a in account_ids]):
        plt.style.use('fivethirtyeight')
        plt.plot(dv[0], dv[1], color=colors[i], linewidth=3, label=account_ids[i], alpha=0.8)
        plt.xlabel('Date')
        plt.xticks(dv[0], rotation='vertical')
        plt.ylabel('USD')
        plt.title('Strategy Comparison {} to {}'.format(dv[0][0], dv[0][-1]))
        plt.legend(prop={'size': 10})
        plt.grid(color='k', alpha=0.4)

    plt.show()


if __name__ == "__main__":
    storage.delete('test:values')
    storage.delete('test:dates')
    for i in range(100):
        storage.rpush('test:values', 1_000_000 + random.randint(0, 10_000))
        storage.rpush('test:dates', i)
    plot_cli()
    storage.delete('test:values')
    storage.delete('test:dates')
