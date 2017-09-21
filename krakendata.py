import pandas as pd
from datetime import datetime
from threading import Thread


from backtrader import DataBase
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                  with_metaclass)
from backtrader import date2num

from krakenstore import KrakenStore

class MetaKrakenData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaKrakenData, cls).__init__(name, bases, dct)

        # Register with the store
        KrakenStore.DataCls = cls

class KrakenData(with_metaclass(MetaKrakenData, DataBase)):
    params = (
        ('historical', False),  # stop loading after backfill load
        ('backfill_start', True),  # do a backfill load when starting up
    )

    _store = KrakenStore

    _ST_IDLE, _ST_FROM, _ST_LIVE, _ST_OVER = range(4)

    def islive(self):
        '''Returns ``True`` to notify ``Cerebro`` that preloading and runonce
        should be deactivated'''
        return True

    def __init__(self, **kwargs):
        self.k = self._store(**kwargs)
        self._state = self._ST_IDLE

    def start(self):
        # Check that the requested timeframe/compression pair is supported
        self.interval = self.k.get_granularity(self._timeframe, self._compression)
        if self.interval is None:
            self._state = self._ST_OVER
            return

        # Check that the requested pair is actually available, and save off the information we get
        # because hey why not?
        self.asset_info = self.k.get_instrument(self.p.dataname)
        if self.asset_info is None:
            self._state = self._ST_OVER
            return

        if self.p.backfill_start:
            # kick it off by requesting all the data
            self._ohlc = self.k.get_ohlc(self.p.dataname, datetime.min, self.interval)
            self._since = self.k.get_source_time()
            self._localsince = datetime.now()
            self._state = self._ST_FROM
            self._fillcur = 0gi

    def stop(self):
        pass

    def _load(self):
        if self._state == self._ST_FROM:
            self.lines.datetime[0] = date2num(self._ohlc.index[self._fillcur])
            self.lines.open[0] = self._ohlc.open.iloc[self._fillcur]
            self.lines.high[0] = self._ohlc.high.iloc[self._fillcur]
            self.lines.low[0] = self._ohlc.low.iloc[self._fillcur]
            self.lines.close[0] = self._ohlc.close.iloc[self._fillcur]
            self.lines.volume[0] = self._ohlc.volume.iloc[self._fillcur]
            self.lines.openinterest[0] = self._ohlc['count'].iloc[self._fillcur]

            self._fillcur += 1
            if self._fillcur < len(self._ohlc.index):
                # We have more backfill data to send
                return True
            else:
                if self.p.historical:
                    return False
                else:
                    self._state = self._ST_LIVE
                    #
                    # Fall-through to return the live data


        if self._state == self._ST_LIVE:
            # TODO: Live. Do a blocking get from a Queue to get our next candle.
            return False