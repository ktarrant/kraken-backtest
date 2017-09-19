from datetime import datetime
import time as _time
import collections
import threading

from backtrader.metabase import MetaParams
from backtrader.utils.py3 import queue, with_metaclass
import backtrader as bt

class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton'''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton


class KrakenStore(with_metaclass(MetaSingleton, object)):
    '''Singleton class wrapping to control the connections to Kraken.
    Params:
      - ``token`` (default:``None``): API access token
      - ``account`` (default: ``None``): account id
      - ``practice`` (default: ``False``): use the test environment
      - ``account_tmout`` (default: ``10.0``): refresh period for account
        value/cash refresh
    '''

    BrokerCls = None  # broker class will autoregister
    DataCls = None  # data class will auto register

    params = (
        ('token', ''),
        ('account', ''),
        ('practice', False),
        ('account_tmout', 10.0),  # account balance refresh timeout
    )

    _DTEPOCH = datetime(1970, 1, 1)
    _ENVPRACTICE = 'practice'
    _ENVLIVE = 'live'

    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self):
        super(KrakenStore, self).__init__()

        self.notifs = collections.deque()  # store notifications for cerebro

        self._env = None  # reference to cerebro for general notifications
        self.broker = None  # broker instance
        self.datas = list()  # datas that have registered over start

        self._orders = collections.OrderedDict()  # map order.ref to oid
        self._ordersrev = collections.OrderedDict()  # map oid to order.ref
        self._transpend = collections.defaultdict(collections.deque)

        self._oenv = self._ENVPRACTICE if self.p.practice else self._ENVLIVE
        # TODO: CREATE KRAKEN API REFERENCE HERE

        self._cash = 0.0
        self._value = 0.0
        self._evt_acct = threading.Event()

    def start(self, data=None, broker=None):
        # Datas require some processing to kickstart data reception
        if data is None and broker is None:
            self.cash = None
            return

        if data is not None:
            self._env = data._env
            # For datas simulate a queue with None to kickstart co
            self.datas.append(data)

            if self.broker is not None:
                self.broker.data_started(data)

        elif broker is not None:
            self.broker = broker
            self.streaming_events( )
            self.broker_threads( )

    def stop(self):
        # signal end of thread
        if self.broker is not None:
            self.q_ordercreate.put(None)
            self.q_orderclose.put(None)
            self.q_account.put(None)

    def put_notification(self, msg, *args, **kwargs):
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # put a mark / threads could still append
        return [x for x in iter(self.notifs.popleft, None)]

    # Kraken supported granularities
    _GRANULARITIES = {
        (bt.TimeFrame.Minutes, 1): 1,
        (bt.TimeFrame.Minutes, 5): 5,
        (bt.TimeFrame.Minutes, 15): 15,
        (bt.TimeFrame.Minutes, 30): 30,
        (bt.TimeFrame.Minutes, 60): 60,
        (bt.TimeFrame.Minutes, 240): 240,
        (bt.TimeFrame.Days, 1): 1440,
        (bt.TimeFrame.Weeks, 1): 10080,
        (bt.TimeFrame.Days, 15): 21600, # weird one - 15 day candle
    }


    def get_positions(self):
        # TODO: Query the current positions from Kraken private API
        poslist = None
        return poslist

    def get_granularity(self, timeframe, compression):
        return self._GRANULARITIES.get((timeframe, compression), None)

    def get_instrument(self, dataname):
        # TODO: Query dataname as an instrument (ticker) and... return info for it I guess? unclear
        return None

    def streaming_events(self, tmout=None):
        q = queue.Queue( )
        kwargs = { 'q': q, 'tmout': tmout }

        t = threading.Thread(target=self._t_streaming_listener, kwargs=kwargs)
        t.daemon = True
        t.start( )

        t = threading.Thread(target=self._t_streaming_events, kwargs=kwargs)
        t.daemon = True
        t.start( )
        return q

    def _t_streaming_listener(self, q, tmout=None):
        while True:
            trans = q.get( )
            self._transaction(trans)

    def _t_streaming_events(self, q, tmout=None):
        if tmout is not None:
            _time.sleep(tmout)

        # streamer = Streamer(q,
        #                     environment=self._oenv,
        #                     access_token=self.p.token,
        #                     headers={ 'X-Accept-Datetime-Format': 'UNIX' })
        #
        # streamer.events(ignore_heartbeat=False)
        # TODO: FIGURE OUT WHAT STREAMING EVENTS IS


    def candles(self, dataname, dtbegin, dtend, timeframe, compression,
                candleFormat, includeFirst):

        kwargs = locals().copy()
        kwargs.pop('self')
        kwargs['q'] = q = queue.Queue()
        t = threading.Thread(target=self._t_candles, kwargs=kwargs)
        t.daemon = True
        t.start()
        return q

    def _t_candles(self, dataname, dtbegin, dtend, timeframe, compression,
                   candleFormat, includeFirst, q):

        granularity = self.get_granularity(timeframe, compression)
        if granularity is None:
            # e = OandaTimeFrameError()
            # q.put(e.error_response)
            # TODO: ENQUEUE AN ERROR HERE
            return

        dtkwargs = {}
        if dtbegin is not None:
            dtkwargs['start'] = int((dtbegin - self._DTEPOCH).total_seconds())

        if dtend is not None:
            dtkwargs['end'] = int((dtend - self._DTEPOCH).total_seconds())

        # try:
        #     response = self.oapi.get_history(instrument=dataname,
        #                                      granularity=granularity,
        #                                      candleFormat=candleFormat,
        #                                      **dtkwargs)
        #
        # except oandapy.OandaError as e:
        #     q.put(e.error_response)
        #     q.put(None)
        #     return
        # TODO: QUERY HISTORY AND ENQUEUE FOUND CANDLES

        # for candle in response.get('candles', []):
        #     q.put(candle)

        q.put({})  # end of transmission

    def streaming_prices(self, dataname, tmout=None):
        q = queue.Queue()
        kwargs = {'q': q, 'dataname': dataname, 'tmout': tmout}
        t = threading.Thread(target=self._t_streaming_prices, kwargs=kwargs)
        t.daemon = True
        t.start()
        return q

    def _t_streaming_prices(self, dataname, q, tmout):
        if tmout is not None:
            _time.sleep(tmout)

        # streamer = Streamer(q, environment=self._oenv,
        #                     access_token=self.p.token,
        #                     headers={'X-Accept-Datetime-Format': 'UNIX'})
        #
        # streamer.rates(self.p.account, instruments=dataname)
        # TODO: FIGURE OUT WHAT STREAMING RATES IS