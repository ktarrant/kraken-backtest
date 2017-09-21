from datetime import datetime
import pandas as pd

from backtrader import DataBase
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                  with_metaclass)
from backtrader import date2num

import krakenex

from krakenstore import KrakenStore

class MetaKrakenData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaKrakenData, cls).__init__(name, bases, dct)

        # Register with the store
        KrakenStore.DataCls = cls

class KrakenData(with_metaclass(MetaKrakenData, DataBase)):
    # params = (
    #     ('qcheck', 3.0),
    #     ('historical', False),  # do backfilling at the start
    #     ('backfill_start', True),  # do backfilling at the start
    #     ('backfill', True),  # do backfilling when reconnecting
    #     ('backfill_from', None),  # additional data source to do backfill from
    # )

    _store = KrakenStore

    def __init__(self, **kwargs):
        self.k = self._store(**kwargs)
        # self._state = self._ST_FROM

    def start(self):
        self._since = datetime.min # kick it off by requesting all the data

        interval = self.k.get_granularity(self._timeframe, self._compression)
        if interval is None:
            return

        # This downloads the live data from Kraken, but at 1-min, only get 12 hours worth
        self._ohlc = self.k.get_ohlc(self.p.dataname, self._since, interval)
        print(self._ohlc)

        self._since = self.k.get_source_time()
        self._icur = 0

    def stop(self):
        self._icur = -1

    def _load(self):
        # sample_table.to_csv(cache_fn)
        if self._icur >= 0:
            self.lines.datetime[0] = date2num(self._ohlc.index[self._icur])
            self.lines.open[0] = self._ohlc.open.iloc[self._icur]
            self.lines.high[0] = self._ohlc.high.iloc[self._icur]
            self.lines.low[0] = self._ohlc.low.iloc[self._icur]
            self.lines.close[0] = self._ohlc.close.iloc[self._icur]
            self.lines.volume[0] = self._ohlc.volume.iloc[self._icur]
            self.lines.openinterest[0] = 0.0

            self._icur += 1
            if self._icur == len(self._ohlc.index):
                return False
            else:
                return True

        else:
            return False