
import argparse
from datetime import datetime, timedelta

from magictrade import storage
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy
from tests.data import human_quotes_1

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
    'short_window_pct': 0.1,
    'med_window': 10,
    'med_window_pct': 100,
    'long_window': 20,
    'long_window_pct': 200,
}


def date_fmt(dt: datetime):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


date = datetime.strptime('1998-01-02', '%Y-%m-%d')
date = datetime.strptime('2019-01-07 09:31:00', '%Y-%m-%d %H:%M:%S')

pmb1 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='Buy and Hold',
                        #data_files=(('SPY', 'SPY_1min_1_7-11_19.csv'),))
                        data=human_quotes_1)
                        #data_files=(('SPY', 'SPY_daily_20yr.csv'),))
pmb2 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='Human',
                        data=human_quotes_1)
                        #data_files=(('SPY', 'SPY_1min_1_7-11_19.csv'),))
                        #data_files=(('SPY', 'SPY_daily_20yr.csv'),))

bhs = BuyandHoldStrategy(pmb1)
hts = HumanTradingStrategy(pmb2, config=CONFIG)

#while date < datetime.today():
#    if pmb1.data['TST']['history'].get(date_fmt(date)):
for i in range(1, 90):
        pmb1.date = date_fmt(date)
        pmb2.date = date_fmt(date)
        pmb1.date = i
        pmb2.date = i
        pmb1.log_balance()
        pmb2.log_balance()
        bhs.make_trade('TST')
        hts.make_trade('TST')
#    date += timedelta(minutes=1)

print("Buys:", storage.get('buy'), "Sells:", storage.get('sell'))
print("Finishing balances:")
print("Buy and Hold:", round(pmb1.cash_balance, 2), round(pmb1.get_value(), 2))
print("Human:", round(pmb2.cash_balance, 2), round(pmb2.get_value(), 2))
