import datetime
import pandas as pd


from backtrader import Cerebro, TimeFrame, WriterFile
from backtrader.feeds import PandasData
from backtrader import Strategy
from backtrader.sizers import PercentSizer

from supertrend import Supertrend

# NOTE: for the (default) 1-minute granularity, the API seems to provide
# data up to 12 hours old only!
# since = str(1499000000) # UTC 2017-07-02 12:53:20
def load_cached_sample(today = datetime.date.today(), pair = 'XXBTZUSD', interval = 15):
    since = datetime.date(2017, 1, 1)
    cache_fn = "{}_{}_{}m.csv".format(today, pair, interval)

    try:
        sample_table = pd.read_csv(cache_fn)
        sample_table['datetime'] = sample_table['datetime'].apply(
            lambda s: datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S'))
        sample_table = sample_table.set_index('datetime')
    except IOError:
        # This downloads the live data from Kraken, but only up to 12 hours worth
        import krakenex
        k = krakenex.API()
        ret = k.query_public('OHLC', req={ 'pair': pair, 'since': since, 'interval': interval})
        ohlc_columns = ['datetime', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count']
        sample_table = pd.DataFrame(data = ret['result'][pair], columns=ohlc_columns)
        sample_table = sample_table.apply(lambda ax: pd.to_numeric(ax, errors='ignore'))
        sample_table['datetime'] = sample_table['datetime'].apply(datetime.datetime.fromtimestamp)
        sample_table = sample_table.set_index('datetime')
        sample_table.to_csv(cache_fn)

    return sample_table

class TestStrategy(Strategy):

    def __init__(self):
        self.st = Supertrend()
        self.last_trend = 0

    def nextstart(self):
        self.order = None
        self.next()

    def next(self):
        if self.order:
            # Already have pending order
            return

        cur_trend = self.st.lines.trend[0]

        if cur_trend != self.last_trend:

            self.close( )  # closes existing position - no matter in which direction
            if cur_trend == 1:
                self.buy()  # enter long
            elif cur_trend == -1:
                self.sell()  # enter short

        self.last_trend = cur_trend

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # The order was either completed or failed in some way
        self.order = None

# Append X to the ticker if it is a crypto, Z if it is a fiat
LONG_CURRENCY = 'XLTC'
SHORT_CURRENCY = 'ZUSD'
PAIR = "{}{}".format(LONG_CURRENCY, SHORT_CURRENCY)
INTERVAL = 60

sample_table = load_cached_sample(pair=PAIR, interval=INTERVAL)

# Create a cerebro entity
cerebro = Cerebro()

# Set our desired cash start
cerebro.broker.setcash(100000.0)

# Set our sizer
cerebro.addsizer(PercentSizer, percents=90)

datafeed = PandasData(dataname=sample_table, timeframe=TimeFrame.Minutes, compression=INTERVAL)
cerebro.adddata(datafeed)

# Add the strategies to run
cerebro.addstrategy(TestStrategy)

# Run the backtest
result = cerebro.run( )

# Plot the result
cerebro.plot( )