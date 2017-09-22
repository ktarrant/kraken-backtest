from datetime import datetime
from threading import Thread
from queue import Queue
import time
import logging

from backtrader import DataBase
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                  with_metaclass)
from backtrader import date2num

from krakenstore import KrakenStore

log = logging.getLogger(__name__)

class MetaKrakenData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaKrakenData, cls).__init__(name, bases, dct)

        # Register with the store
        KrakenStore.DataCls = cls

class KrakenData(with_metaclass(MetaKrakenData, DataBase)):
    params = (
        ('refresh_period', 60.0), # refresh period in seconds
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
            log.error("Unsupported granularity: {} , {}".format(self._timeframe, self._compression))
            self._state = self._ST_OVER
            return

        # Check that the requested pair is actually available, and save off the information we get
        # because hey why not?
        self.asset_info = self.k.get_instrument(self.p.dataname)
        if self.asset_info is None:
            log.error("Invalid dataname: {}".format(self.p.dataname))
            self._state = self._ST_OVER
            return

        if self.p.backfill_start:
            # kick it off by requesting all the data
            self._lastdate = datetime.min
            self._ohlc = self.k.get_ohlc(self.p.dataname, self._lastdate, self.interval)
            self._state = self._ST_FROM
            self._fillcur = 0

        elif not self.p.historical:
            self._state = self._ST_LIVE
            self._lastdate = self.k.get_source_time()
            self._start_live()

        else:
            self._state = self._ST_OVER

    def stop(self):
        self._state = self._ST_OVER

    def _load(self):
        if self._state == self._ST_FROM:
            self._lastdate = self._ohlc.index[self._fillcur]
            self._lastrow = self._ohlc.loc[self._lastdate]
            self._load_row(self._lastrow)

            self._fillcur += 1
            if self._fillcur < len(self._ohlc.index):
                # We have more backfill data to send
                return True
            else:
                if self.p.historical:
                    self._state = self._ST_OVER
                    return False
                else:
                    self._state = self._ST_LIVE
                    self._start_live()
                    #
                    # Fall-through to return the live data


        if self._state == self._ST_LIVE:
            try:
                self._load_row(self._q.get())
                log.debug("Loaded new candle: {}\n{}".format(self._lastdate, self._lastrow))
                return self._state == self._ST_LIVE
            except KeyboardInterrupt:
                log.error("Exiting live data feed")
                self._state = self._ST_OVER
                return False

    def _start_live(self):
        # start up the streamer
        log.info("Starting live thread: {}".format(self._lastdate))
        self._q = Queue()
        self._th = Thread(target=self._t_refresh, daemon=True)
        self._th.start()

    def _t_refresh(self):
        refresh_period = self.p.refresh_period
        def g_tick():
            t = time.time()
            count = 0
            while True:
                count += 1
                yield max(t + count * refresh_period - time.time(), 0)

        g = g_tick()
        while self._state == self._ST_LIVE:
            time.sleep(next(g))
            # Do data load here
            ohlc_new = self.k.get_ohlc(self.p.dataname, self._lastdate, self.interval)
            if len(ohlc_new.index) < 2:
                # the latest incomplete bar is always the last index, but we only want complete
                # bars to add (at least until we figure out if we can update the current candle
                # multiple times?)
                continue

            complete_bars = ohlc_new.index[:-1]
            for dt in complete_bars:
                if dt > self._lastdate:
                    self._lastdate = dt
                    self._lastrow = ohlc_new.loc[dt]
                    self._q.put(self._lastrow)

    def _load_row(self, row):
        self.lines.datetime[0] = date2num(row.name)
        self.lines.open[0] = row.open
        self.lines.high[0] = row.high
        self.lines.low[0] = row.low
        self.lines.close[0] = row.close
        self.lines.volume[0] = row.volume
        self.lines.openinterest[0] = row['count']
