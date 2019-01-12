from datetime import datetime, timedelta

from magictrade.broker.papermoney import PaperMoneyBroker
from magictrade.strategy.buyandhold import BuyandHoldStrategy


def date_fmt(dt: datetime):
    return dt.strftime('%Y-%m-%d')


date = datetime.strptime('1998-01-02', '%Y-%m-%d')
pmb1 = PaperMoneyBroker(date=date_fmt(date),
                        account_id='bah',
                        data_files=(('SPY', 'SPY_daily_20yr.csv'),))

bhs = BuyandHoldStrategy(pmb1)

while date < datetime.today():
    if pmb1.data['SPY']['history'].get(date_fmt(date)):
        print("Trading", date)
        pmb1.date = date_fmt(date)
        pmb1.log_balance(date_fmt(date))
        bhs.make_trade('SPY')
    date += timedelta(days=1)
