import logging

from sulaco.utils.receiver import message_receiver, INTERNAL_SIGN
from sulaco.utils import get_pairs

from location import UserId


logger = logging.getLogger(__name__)

user_idents_key = 'user_idents'

class Root(object):
    #TODO: try to use only atomic db operations


    def __init__(self, gateway, location_config, db):
        self._gateway = gateway
        self._config = location_config
        self._ident = location_config.ident
        self._db = db

    def get_current_state(self):
        cli = self._db.get_client()
        #TODO: use redis scripting
        uids = yield cli.smembers(user_idents_key)
        ret = yield [cli.hgetall(uid) for uid in uids] # pipelining
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
        bulk = [cli.hmset(UserId(uid), user),
                cli.sadd(user_idents_key, UserId(uid))]
        yield bulk
        state = yield from self.get_current_state()
        self._gateway.prs(uid).init(state=state)
        self._gateway.pubs.user_connected(user=user)

    @message_receiver(INTERNAL_SIGN)
    def move_to(self, uid, target_location):
        cli = self._db.get_client()
        yield [cli.delete(UserId(uid)), cli.srem(user_idents_key, UserId(uid))]
        self._gateway.prs(uid).enter(location=target_location)
        self._gateway.pubs.user_disconnected(uid=uid)



