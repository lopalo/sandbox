import logging
import uuid

from sulaco.utils.receiver import message_receiver, INTERNAL_SIGN, USER_SIGN

from location.db import (
    UserId, WorkId, USER_IDENTS_KEY,
    unpack_hash, pack_hash)
from location.work import get_ts, Work
from utils.debugging import debug_func


logger = logging.getLogger(__name__)


def user_view(user):
    FIELDS = ('name', 'uid', 'pos',)
    return {k: v for k, v in user.items() if k in FIELDS}


class Root(object):
    ###
    # WARNING: try to use only atomic db operations, otherwise use redis lock
    ###

    #TODO: Resolve race condition in synchronization between frontend and location

    #TODO: Resolve trouble with sleeping users,
    #      that remained in db and already disconnected (or fronted lost).
    #      May be use periodic checker of activity

    def __init__(self, gateway, location_config, db):
        self._gateway = gateway
        self._config = location_config
        self._ident = location_config.ident
        self._db = db
        self.work_handlers = None # setup later

    def get_current_state(self):
        ret = yield from self._db.get_all_objects(USER_IDENTS_KEY)
        users = [user_view(unpack_hash(i)) for i in ret]
        return dict(ident=self._ident,
                    users=users)

    def start_work(self, *, object_id, work_handler, duration,
                    start_val=None, finish_val=None, info=None):
        if work_handler not in self.work_handlers:
            raise AssertionError("Unknown work handler '{}'" \
                                        .format(work_handler))
        start_ts = get_ts()
        ident = WorkId(uuid.uuid4().hex)
        work = Work(ident=str(ident),
                    object_id=str(object_id),
                    work_handler=work_handler,
                    start_ts=start_ts,
                    finish_ts=start_ts + duration,
                    last_ts=start_ts,
                    start_val=start_val,
                    finish_val=finish_val,
                    info=info)
        yield from self._db.start_work(ident, start_ts,
                    args=pack_hash(work.as_plain()))
        self._gateway.pubs.new_work(work=work.as_plain())
        return work

    def cancel_work(self, work_id):
        #TODO: implement
        pass


    @message_receiver(INTERNAL_SIGN)
    def enter(self, user, uid, prev_loc):
        if prev_loc in (self._ident, None):
            pos = (0, 0)
        else:
            #TODO: set position depending on id of previous location
            pos = (0, 0)
        user['pos'] = pos

        cli = self._db.get_client()
        cli.multi(),
        cli.hmset(UserId(uid), pack_hash(user, to_dict=True)),
        cli.sadd(USER_IDENTS_KEY, UserId(uid)),
        yield from cli.execute()

        state = yield from self.get_current_state()
        self._gateway.prs(uid).init(state=state)
        self._gateway.pubs.user_connected(user=user_view(user))

    @message_receiver(USER_SIGN)
    def move_to(self, uid, target_location):
        #TODO: move to subgenerator "delete_user"

        cli = self._db.get_client()
        cli.multi(),
        cli.delete(UserId(uid)),
        cli.srem(USER_IDENTS_KEY, UserId(uid)),
        yield from cli.execute()

        self._gateway.pubs.user_disconnected(uid=uid)
        ####
        self._gateway.prs(uid).enter(location=target_location)

    @message_receiver(INTERNAL_SIGN)
    def update_user(self, uid, user):
        #TODO: resolve rewriting of user's state, use difference instead
        ret = yield from self._db.update_hash_exists(UserId(uid),
                                           args=pack_hash(user))
        if ret == 1:
            self._gateway.pubs.user_updated(user=user_view(user))

    @debug_func
    @message_receiver(USER_SIGN)
    def increase_stones(self, uid, duration, amount):
        uid = UserId(uid)
        stones = int((yield from self._db.hget(uid, 'stones')))
        yield from self.start_work(object_id=uid,
                                   work_handler='incr_stones',
                                   duration=duration,
                                   start_val=stones,
                                   finish_val=stones + amount)






