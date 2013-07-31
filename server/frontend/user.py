import hashlib
import logging
import msgpack

from copy import deepcopy
from steward import Component, Field

from sulaco.utils import Sender
from sulaco.utils.receiver import message_receiver, USER_SIGN, INTERNAL_SIGN

from utils.debugging import debug_func


logger = logging.getLogger(__name__)


class LocInputSocket(object):

    def __init__(self, uid, sock):
        self._sock = sock
        self._uid = uid
        self.s = Sender(self.send)

    def send(self, msg, sign=INTERNAL_SIGN):
        msg['kwargs']['uid'] = self._uid
        msg['sign'] = sign
        self._sock.send(msgpack.dumps(msg))


class User(Component):
    frontend_id = Field()
    uid = Field()
    name = Field()
    location = Field()
    password_hash = Field()

    stones = Field(default=0)

    def setup(self, *, db, connman, msgman):
        self._db = db
        self._connman = connman
        self._msgman = msgman

    def snapshot(self):
        self._copy = deepcopy(self.as_plain())
        self._cli_view_copy = deepcopy(self.client_view())
        self._loc_view_copy = deepcopy(self.location_view())

    def finalize(self, *, update_client=True, update_location=True):
        if self._copy == self.as_plain():
            return
        yield from self.save()
        if update_client and self.conn is not None \
                and self._cli_view_copy != self.client_view():
            self.conn.s.user.basic_info(data=self.client_view())
        if update_location and self.loc_conn is not None \
                and self._loc_view_copy != self.location_view():
            self.loc_conn.s.update_user(user=self.location_view())
        self.snapshot()

    def save(self):
        yield from self._db[self.uid].hset(self.uid, 'basic',
                                msgpack.dumps(self.as_plain()))
        logger.debug("User %s saved", self.uid)

    def check_frontend(self, frontend_id):
        if frontend_id == self.frontend_id:
            return True
        if self.conn is not None:
            self.conn.close()
        logger.info("User '%s' has wrong frontend ident", self.uid)
        return False

    @staticmethod
    def generate_password_hash(password):
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @classmethod
    def load(cls, uid, db):
        packed = yield from db[uid].hget(uid, 'basic')
        return cls(**msgpack.loads(packed, encoding='utf-8'))

    def client_view(self):
        return {'uid': self.uid,
                'name': self.name,
                'stones': self.stones}

    def location_view(self):
        return {'uid': self.uid,
                'name': self.name,
                'stones': self.stones}

    @property
    def conn(self):
        return self._connman.get_connection(self.uid)

    @property
    def loc_conn(self):
        if self.location not in self._msgman.loc_input_sockets:
            return
        socket = self._msgman.loc_input_sockets[self.location]
        return self.wrap_loc_socket(socket)

    def wrap_loc_socket(self, sock):
        return LocInputSocket(self.uid, sock)

    @message_receiver(USER_SIGN)
    def get_basic_info(self, conn, **kwargs):
        conn.s.user.basic_info(data=self.client_view())

    @debug_func
    @message_receiver(USER_SIGN)
    def change_field(self, name, value, **kwargs):
        assert hasattr(self, name), name
        setattr(self, name, value)


