import datetime
import pandas as pd


from backtrader import Cerebro, TimeFrame, WriterFile
from backtrader import Strategy
from backtrader.sizers import PercentSizer

from supertrend import Supertrend
from krakendata import KrakenData

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

            self.close()  # closes existing position - no matter in which direction
            if cur_trend == 1:
                self.buy()  # enter long
                print("LONG")
            elif cur_trend == -1:
                self.sell()  # enter short
                print("SHORT")

        self.last_trend = cur_trend

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # The order was either completed or failed in some way
        self.order = None

# Append X to the ticker if it is a crypto, Z if it is a fiat
LONG_CURRENCY = 'XXBT'
SHORT_CURRENCY = 'ZUSD'
PAIR = "{}{}".format(LONG_CURRENCY, SHORT_CURRENCY)
INTERVAL = 1

# Create a cerebro entity
cerebro = Cerebro()

# Set our desired cash start
cerebro.broker.setcash(100000.0)

# Set our sizer
cerebro.addsizer(PercentSizer, percents=90)

# Load the Kraken data
datafeed = KrakenData(dataname=PAIR, timeframe=TimeFrame.Minutes, compression=INTERVAL)
cerebro.adddata(datafeed)

# Add the strategies to run
cerebro.addstrategy(TestStrategy)

# Run the backtest
result = cerebro.run()

# Plot the result
cerebro.plot()