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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="test kraken store and data")
    parser.add_argument("--long", default="XXBT", help="symbol to long")
    parser.add_argument("--short", default="ZUSD", help="symbol to short")
    parser.add_argument("--timeframe", choices=['Minutes', 'Days', 'Weeks'], default='Minutes')
    parser.add_argument("--compression", default=60, type=int)
    parser.add_argument("--refresh", default=60, help="data refresh period in 60 seconds")
    parser.add_argument("--historical", action='store_true', help="only run backfill, no live")
    parser.add_argument("--no-backfill", action='store_true', help="skip backfill, only live")
    args = parser.parse_args()

    # Create a cerebro entity
    cerebro = Cerebro()

    # Set our desired cash start
    cerebro.broker.setcash(100000.0)

    # Set our sizer
    cerebro.addsizer(PercentSizer, percents=90)

    # Load the Kraken data
    pair = args.long + args.short
    datafeed = KrakenData(dataname=pair,
                          timeframe=getattr(TimeFrame, args.timeframe),
                          compression=args.compression,
                          refresh_period=args.refresh,
                          historical=args.historical,
                          backfill_start=not args.no_backfill)
    cerebro.adddata(datafeed)

    # Add the strategies to run
    cerebro.addstrategy(TestStrategy)

    # Run the backtest
    result = cerebro.run()

    # Plot the result
    cerebro.plot()