import argparse
from datetime import datetime, timedelta

from magictrade import storage
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy
from magictrade.utils import plot_account_balances, get_percentage_change

parser = argparse.ArgumentParser(description='Plot results of trading algorithms.')
parser.add_argument('-m', dest='momentum', type=float)
args = parser.parse_args()

storage.flushdb()

CONFIG = {
    'peak_window': 30,
    'sample_frequency_minutes': 5,
    'stop_loss_pct': 10,
    'take_gain_pct': 20,
    'max_equity': 1_000_000,
    'short_window': 5,
    'short_window_pct': 0.09,
    'med_window': 10,
    'med_window_pct': 150,
    'long_window': 20,
    'long_window_pct': 200,
}


def date_fmt(dt: datetime):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


date = datetime.strptime('1998-01-02', '%Y-%m-%d')
date = datetime.strptime('2019-01-07 09:31:00', '%Y-%m-%d %H:%M:%S')

pmb1 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='Buy and Hold',
                        data_files=(('SPY', 'SPY_1min_1_7-11_19_2.csv'),))
# data_files=(('SPY', 'SPY_daily_20yr.csv'),))
pmb2 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='Human',
                        data_files=(('SPY', 'SPY_1min_1_7-11_19_2.csv'),))
# data_files=(('SPY', 'SPY_daily_20yr.csv'),))

bhs = BuyandHoldStrategy(pmb1)
hts = HumanTradingStrategy(pmb2, config=CONFIG)

while date < datetime.strptime('2019-01-12', '%Y-%m-%d'):
    if pmb1.data['SPY']['history'].get(date_fmt(date)):
        pmb1.date = date_fmt(date)
        pmb2.date = date_fmt(date)
        pmb1.log_balance()
        pmb2.log_balance()
        bhs.make_trade('SPY')
        hts.make_trade('SPY')
        print(date, hts._get_window_change('SPY', 'short'))
        t = hts.trades.get(date_fmt(date))
        if t:
            print(t)

    date += timedelta(minutes=1)

print("Buys:", storage.get('buy'), "Sells:", storage.get('sell'))
print("Finishing balances:")
print("Buy and Hold:", round(pmb1.balance, 2), round(pmb1.get_value(), 2))
print("Human:", round(pmb2.balance, 2), round(pmb2.get_value(), 2))
print("Advantage: {:.2%}, Total: {:.2%}".format(get_percentage_change(pmb1.get_value(), pmb2.get_value()) / 100,
                                                get_percentage_change(1_000_000, pmb2.get_value()) / 100))
plot_account_balances(['Buy and Hold', 'Human'], trades=hts.trades, graph_ticks=350)
