import logging
import uuid
import msgpack

from random import choice

from sulaco.outer_server.message_manager import LocationRoot
from sulaco.utils.receiver import (
    message_receiver, message_router, LoopbackMixin,
    USER_SIGN, INTERNAL_USER_SIGN, INTERNAL_SIGN)
from sulaco.utils.lock import Lock

from frontend.user import User
from frontend.location import Location


logger = logging.getLogger(__name__)


class Root(LocationRoot, LoopbackMixin):
    #TODO: more info logs

    def __init__(self, config, game_config, connman, msgman, dbs):
        super().__init__()
        self._config = config
        self._game_config = game_config
        self._connman = connman
        self._msgman = msgman
        self._db = dbs['nodes']
        self._name_db = dbs['name_db']
        self._frontend_id = 'frontend_id:' + uuid.uuid4().hex
        self._lock = Lock()
        self._locations = {}

    @message_receiver()
    def register(self, username, password, conn, **kwargs):
        assert username != 'db_name'
        exists = yield from self._name_db.exists(username)
        if exists:
            conn.s.auth.error(text='username exists')
            return
        uid = 'uid:' + uuid.uuid4().hex
        loc_id = choice(self.start_locations)
        user = User(uid=uid,
                    name=username,
                    location=loc_id,
                    password_hash=User.generate_password_hash(password),
                    frontend_id=self._frontend_id)
        user.setup(db=self._db,
                   connman=self._connman,
                   msgman=self._msgman)
        self._connman.bind_connection_to_uid(conn, uid)
        yield from user.save()
        yield from self._name_db.set(username, uid)
        conn.s.user.basic_info(data=user.client_view())
        self.lbs.location.enter(uid=uid)

    @message_receiver()
    def sign_in(self, username, password, conn, **kwargs):
        uid = yield from self._name_db.get(username)
        if uid is None:
            conn.s.auth.error(text='unknown username')
            return
        uid = uid.decode('utf-8')
        with (yield from self._lock.atomic(uid)):
            user = yield from User.load(uid, self._db)
            user.setup(db=self._db,
                       connman=self._connman,
                       msgman=self._msgman)
            if user.password_hash != User.generate_password_hash(password):
                conn.s.auth.error(text='wrong username or password')
                return
            user.frontend_id = self._frontend_id
            self._connman.bind_connection_to_uid(conn, uid)
            yield from user.save()
        conn.s.user.basic_info(data=user.client_view())
        self.lbs.location.enter(uid=uid)

    @message_router(USER_SIGN)
    def user(self, next_step, uid, **kwargs):
        conn = self._connman.get_connection(uid)
        with (yield from self._lock.atomic(uid)):
            user = yield from User.load(uid, self._db)
            user.setup(db=self._db,
                       connman=self._connman,
                       msgman=self._msgman)
            user.snapshot()
            if not user.check_frontend(self._frontend_id):
                return
            yield from next_step(user)
            yield from user.finalize()

    def location_added(self, loc_id, data):
        self._locations[loc_id] = data

    def location_removed(self, loc_id):
        del self._locations[loc_id]

    @property
    def start_locations(self):
        st_locs = set(self._game_config.user.start_locations)
        avail_locs = set(self._locations)
        return list(st_locs & avail_locs)

    @message_router(INTERNAL_USER_SIGN, pass_sign=True)
    def location(self, next_step, sign, uid, location=None,
                                _update_in_loc=True, **kwargs):
        with (yield from self._lock.atomic(uid)):
            #TODO: use Location.step_is_proxy(next_step) to decide to load user
            user = yield from User.load(uid, self._db)
            user.setup(db=self._db,
                       connman=self._connman,
                       msgman=self._msgman)
            user.snapshot()
            if not user.check_frontend(self._frontend_id):
                return

            if sign == INTERNAL_SIGN:
                loc_id = location or user.location
            else:
                loc_id = user.location

            if loc_id not in self._locations:
                #TODO: test this case
                new_loc_id = choice(self.start_locations)
                self.lbs.location.enter(uid=uid, location=new_loc_id)
                return

            socket = self._msgman.loc_input_sockets[loc_id]
            socket = user.wrap_loc_socket(socket)
            location = Location(ident=loc_id,
                                user=user,
                                loc_input=socket,
                                connman=self._connman,
                                config=self._config)
            yield from next_step(location)
            yield from user.finalize(update_location=_update_in_loc)

