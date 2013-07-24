import time
import logging

from steward import Component, Field
from tornado.gen import coroutine

from location.db import unpack_hash


logger = logging.getLogger(__name__)

get_ts = lambda: time.time() + time.timezone


class WorkHandler(Component):
    """ Should be loaded from yaml file """
    #TODO: unit tests

    #TODO: check on load
    AVAILABLE_TRANSITIONS = ('lineral',)

    ident = Field()
    transition = Field(default='lineral')
    ticks = Field(default=4)

    def process(self, work):
        """ Returns timestamp of next update or None to cancel the work """

        ts = get_ts()
        ts = max(min(ts, work.finish_ts), work.start_ts)
        last_ft = self.value_factor(work.time_factor(work.last_ts))
        ft = self.value_factor(work.time_factor(ts))
        delta = work.delta * (ft - last_ft) if work.delta is not None else None
        last_tick = ts == work.finish_ts
        cont = yield from self.accept(work, ft, delta, last_tick)
        if last_tick or not cont:
            return
        work.last_ts = ts
        return min(ts + work.duration / self.ticks, work.finish_ts)

    def value_factor(self, time_factor):
        assert 0 <= time_factor <= 1, time_factor
        if self.transition == 'lineral':
            return time_factor

    def accept(self, work, ft, delta, last_tick):
        """ Should return True to continue """
        #return True
        logger.debug("Accepting (ident: %s, object: %s, factor: %s, "
                     "delta: %s, last_tick: %s", self.ident, work.object_id,
                                                 ft, delta, last_tick)
        return True

    def setup(self, db, gateway):
        self._db = db
        self._gateway = gateway


class IncrFieldHandler(WorkHandler):
    field = Field() # 'hp, stones, ...'

    def accept(self, work, ft, delta, last_tick):
        super().accept(work, ft, delta, last_tick)
        val = yield self._db.hincrbyfloat(work.object_id, self.field, delta)
        val = round(float(val))
        if last_tick:
            prefix, ident = work.object_id.split(':', 1)
            if prefix == 'user':
                self._gateway.prs(ident).update_field(field=self.field,
                                                      value=val)
        return True


class WalkHandler(WorkHandler):

    def accept(self, work, ft, delta, last_tick):
        super().accept(work, ft, delta, last_tick)
        #TODO: check obstacles and calculate and serialize new_pos
        new_pos = (1, 1)
        yield self._db.hset(work.object_id, 'pos', new_pos)
        if last_tick:
            #TODO: send to frontend
            pass
        return True


class Work(Component):
    """ Should be saved in redis """
    object_id = Field()
    ident = Field()
    work_handler = Field()

    start_ts = Field()
    finish_ts = Field()

    last_ts = Field() # last update

    start_val = Field()
    finish_val = Field()
    info = Field(default=None)

    @property
    def duration(self):
        return self.finish_ts - self.start_ts

    def time_factor(self, ts):
        return (ts - self.start_ts) / self.duration

    @property
    def delta(self):
        if not isinstance(self.start_val, (int, float)) \
                or not isinstance(self.finish_val, (int, float)):
            return
        return self.finish_val - self.start_val


@coroutine
def process_ticks(db, work_handlers, works_per_step=10):
    try:
        while True:
            ts = get_ts()
            work_lst = yield db.get_work_list(ts, works_per_step)
            for w in work_lst:
                w = Work.from_plain(unpack_hash(w))
                handler = work_handlers[w.work_handler]
                next_ts = yield from handler.process(w)
                if next_ts is None:
                    yield db.cancel_work(w.ident)
                else:
                    yield db.continue_work(w.ident, next_ts, w.last_ts)
    except:
        logger.exception('Exception in tick processor:')


def get_work_handlers():
    #TODO: do it in metaclass
    from inspect import isclass
    for v in globals().values():
        if not isclass(v) or not issubclass(v, WorkHandler):
            continue
        yield v.__name__, v


work_handlers = dict(get_work_handlers())

