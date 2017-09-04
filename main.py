import datetime
import pandas as pd


from backtrader import Cerebro, TimeFrame, WriterFile
from backtrader.feeds import GenericCSVData

pair = 'XETHZEUR'
# NOTE: for the (default) 1-minute granularity, the API seems to provide
# data up to 12 hours old only!
# since = str(1499000000) # UTC 2017-07-02 12:53:20
since = datetime.date(2017, 1, 1)

# # This downloads the live data from Kraken, but only up to 12 hours worth
# import krakenex
# k = krakenex.API()
# ret = k.query_public('OHLC', req={ 'pair': pair, 'since': since })
# ohlc_columns = ['datetime', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count']
# sample_table = pd.DataFrame(data = ret['result'][pair], columns=ohlc_columns)
# sample_table = sample_table.apply(lambda ax: pd.to_numeric(ax, errors='ignore'))
# sample_table['datetime'] = sample_table['datetime'].apply(datetime.datetime.fromtimestamp)
# sample_table = sample_table.set_index('datetime')
# print(sample_table)
# # print(ret)

# table = pd.read_csv('krakenUSD.csv')
# table.columns = ['datetime', 'price', 'volume']
# table['datetime'] = table['datetime'].apply(datetime.datetime.fromtimestamp)
# print(table)

# Create a cerebro entity
cerebro = Cerebro()

# Set our desired cash start
cerebro.broker.setcash(100000.0)

data = GenericCSVData(
        dataname='krakenUSD.csv',
        dtformat=1, # unix timestamp (int)
        timeframe=TimeFrame.Ticks,
        datetime=0,
        close=1,
        volume=2,
        open=-1,
        high=-1,
        low=-1,
        openinterest=-1,
)
resampled = cerebro.resampledata(data, TimeFrame.Minutes)

# cerebro.addwriter(WriterFile, csv=True)

# cerebro.adddata(data)

# Run the backtest
cerebro.run()

# Plot the result
cerebro.plot()