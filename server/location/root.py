import logging

from itertools import chain
from sulaco.utils.receiver import message_receiver, INTERNAL_SIGN
from sulaco.utils import get_pairs

from location.db import UserId, user_idents_key


logger = logging.getLogger(__name__)


class Root(object):
    ###
    # WARNING: try to use only atomic db operations, otherwise use redis lock
    ###

    def __init__(self, gateway, location_config, db):
        self._gateway = gateway
        self._config = location_config
        self._ident = location_config.ident
        self._db = db

    def get_current_state(self):
        ret = yield self._db.get_all_users()
        #TODO: unpack users correctly (now returns byte strings)
        # and check in test
        users = [dict(get_pairs(i)) for i in ret]
        return dict(ident=self._ident,
                    users=users)

    @message_receiver(INTERNAL_SIGN)
    def enter(self, user, uid, prev_loc):
        if prev_loc in (self._ident, None):
            pos = (0, 0)
        else:
            #TODO: set position depending on id of previous location
            pos = (0, 0)
        user['pos'] = pos
        cli = self._db.get_client()
        # pipelining
        yield [cli.multi(),
               cli.hmset(UserId(uid), user), #TODO: pack user correctly
               cli.sadd(user_idents_key, UserId(uid)),
               cli.execute()]
        state = yield from self.get_current_state()
        self._gateway.prs(uid).init(state=state)
        self._gateway.pubs.user_connected(user=user)

    @message_receiver(INTERNAL_SIGN)
    def move_to(self, uid, target_location):
        cli = self._db.get_client()
        yield [cli.multi(),
               cli.delete(UserId(uid)),
               cli.srem(user_idents_key, UserId(uid)),
               cli.execute()]
        self._gateway.prs(uid).enter(location=target_location)
        self._gateway.pubs.user_disconnected(uid=uid)

    @message_receiver(INTERNAL_SIGN)
    def update_user(self, uid, user):
        ret = yield self._db.update_hash_exists(UserId(uid),
                               args=list(chain(*user.items())))
        if ret == 1:
            self._gateway.pubs.user_updated(user=user)



