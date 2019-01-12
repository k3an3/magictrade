import argparse
from datetime import datetime, timedelta

from magictrade import storage
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy
from magictrade.utils import plot_account_balances

parser = argparse.ArgumentParser(description='Plot results of trading algorithms.')
parser.add_argument('-m', dest='momentum', type=float)
args = parser.parse_args()

CONFIG = {
    'security_type': 'stock',
    'exp_days': 30,  # options
    'strike_dist': 5,  # options
    'momentum_slope': args.momentum,
    'momentum_window_samples': 10,
    'sample_frequency_minutes': 5,
    'stop_loss_percent': 10,
    'stop_loss_take_gain_percent': 20,
    'max_equity': 1_000_000,
}


def date_fmt(dt: datetime):
    return dt.strftime('%Y-%m-%d')


date = datetime.strptime('1998-01-02', '%Y-%m-%d')
storage.delete("Buy and Hold:dates")
storage.delete("Buy and Hold:values")
storage.delete("Human:dates")
storage.delete("Human:values")
storage.delete("SPY")
storage.delete("buy")
storage.delete("sell")
pmb1 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='Buy and Hold',
                        data_files=(('SPY', 'SPY_daily_20yr.csv'),))
pmb2 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='Human',
                        data_files=(('SPY', 'SPY_daily_20yr.csv'),))

bhs = BuyandHoldStrategy(pmb1)
hts = HumanTradingStrategy(pmb2, config=CONFIG)

while date < datetime.today():
    if pmb1.data['SPY']['history'].get(date_fmt(date)):
        pmb1.date = date_fmt(date)
        pmb2.date = date_fmt(date)
        pmb1.log_balance(date_fmt(date))
        pmb2.log_balance(date_fmt(date))
        bhs.make_trade('SPY')
        hts.make_trade('SPY')
    date += timedelta(days=1)

print("{} buys, {} sells".format(storage.get('buy'), storage.get('sell')))
plot_account_balances([pmb1.account_id, pmb2.account_id])
