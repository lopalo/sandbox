import logging
import uuid
import msgpack

from sulaco.outer_server.message_manager import LocationRoot
from sulaco.utils.receiver import (
    message_receiver, message_router, LoopbackMixin,
    ProxyMixin, USER_SIGN, INTERNAL_USER_SIGN, INTERNAL_SIGN)
from sulaco.utils.lock import Lock

from frontend.user import User


logger = logging.getLogger(__name__)


class Root(LocationRoot, LoopbackMixin):

    def __init__(self, config, connman, msgman, dbs):
        super().__init__()
        self._config = config
        self._connman = connman
        self._msgman = msgman
        self._db = dbs['nodes']
        self._name_db = dbs['name_db']
        self._frontend_id = 'frontend_id:' + uuid.uuid4().hex
        self._lock = Lock()

    @message_receiver()
    def register(self, username, password, conn, **kwargs):
        #TODO: remove showing of password from log
        assert username != 'db_name'
        exists = yield self._name_db.exists(username)
        if exists:
            conn.s.auth.error(text='username exists')
            return
        uid = 'uid:' + uuid.uuid4().hex
        user = User(uid=uid,
                    name=username,
                    password_hash=User.generate_password_hash(password),
                    frontend_id=self._frontend_id)
        self._connman.bind_connection_to_uid(conn, uid)
        yield from user.save(self._db)
        yield self._name_db.set(username, uid)
        conn.s.user.basic_info(data=user.json_view())

    @message_receiver()
    def sign_in(self, username, password, conn, **kwargs):
        #TODO: remove showing of password from log
        uid = yield self._name_db.get(username)
        if uid is None:
            conn.s.auth.error(text='unknown username')
            return
        uid = uid.decode('utf-8')
        yield from self._lock.acquire(uid)
        try:
            user = yield from User.load(uid, self._db)
            if user.password_hash != User.generate_password_hash(password):
                conn.s.auth.error(text='wrong username or password')
                return
            user.frontend_id = self._frontend_id
            self._connman.bind_connection_to_uid(conn, uid)
            yield from user.save(self._db)
        finally:
            self._lock.release(uid)
        conn.s.user.basic_info(data=user.json_view())

    @message_router(USER_SIGN)
    def user(self, next_step, conn, uid, **kwargs):
        yield from self._lock.acquire(uid)
        try:
            user = yield from User.load(uid, self._db)
            if self._frontend_id != user.frontend_id:
                conn.close()
                logger.info("User '%s' has wrong frontend ident", user.uid)
                return
            yield from next_step(user)
            if user.need_save:
                yield from user.save(self._db)
        finally:
            self._lock.release(uid)


    def location_added(self, loc_id):
        pass

    def location_removed(self, loc_id):
        pass

