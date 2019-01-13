
import argparse
from datetime import datetime, timedelta

from magictrade import storage
from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy
from magictrade.strategy.human import HumanTradingStrategy

parser = argparse.ArgumentParser(description='Plot results of trading algorithms.')
parser.add_argument('-m', dest='momentum', type=float)
args = parser.parse_args()

storage.flushdb()

for i in [x * 0.05 for x in range(0, 100)]:

    CONFIG = {
        'security_type': 'stock',
        'exp_days': 30,  # options
        'strike_dist': 5,  # options
        'momentum_slope': i,
        'momentum_window_samples': 10,
        'sample_frequency_minutes': 5,
        'stop_loss_percent': 10,
        'stop_loss_take_gain_percent': 20,
        'max_equity': 100_000_000,
    }


    def date_fmt(dt: datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')


    date = datetime.strptime('1998-01-02', '%Y-%m-%d')
    date = datetime.strptime('2019-01-07 09:31:00', '%Y-%m-%d %H:%M:%S')

    pmb1 = PaperMoneyBroker(date=date_fmt(date),
                            account_id='Buy and Hold',
                            data_files=(('SPY', 'SPY_1min_1_7-11_19.csv'),))
                            #data_files=(('SPY', 'SPY_daily_20yr.csv'),))
    pmb2 = PaperMoneyBroker(date=date_fmt(date),
                            account_id='Human' + str(i),
                            data_files=(('SPY', 'SPY_1min_1_7-11_19.csv'),))
                            #data_files=(('SPY', 'SPY_daily_20yr.csv'),))

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
        date += timedelta(minutes=1)

    print("{}: {} buys, {} sells".format(i, storage.get('buy'), storage.get('sell')))
    print("Using {}, got bah {} and hts {}".format(round(i, 2), pmb1.get_value(), pmb2.get_value()))
