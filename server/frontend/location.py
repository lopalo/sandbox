import msgpack

from sulaco.utils import Sender
from sulaco.utils.receiver import (
    message_receiver, ProxyMixin, USER_SIGN,
    INTERNAL_USER_SIGN, INTERNAL_SIGN)


class Location(ProxyMixin):

    def __init__(self, *, ident, user, loc_input, connman, config):
        self._ident = ident
        self._user = user
        self._loc_input = loc_input
        self._connman = connman
        self._config = config
        self.s = Sender(self.send)

    def send(self, msg):
        msg['kwargs']['uid'] = self._user.uid
        self._loc_input.send(msgpack.dumps(msg))

    @message_receiver(INTERNAL_SIGN)
    def enter(self, **kwargs):
        connman = self._connman
        user = self._user
        conn = connman.get_connection(user.uid)
        if conn is None:
            return
        prev_loc = user.location
        if user.location is not None and user.location != self._ident:
            connman.remove_user_from_location(user.location, user.uid)
        user.location = self._ident
        user.mark_save()
        connman.add_user_to_location(self._ident, user.uid)
        self.s.enter(user=user.json_view(), prev_loc=prev_loc)

    def proxy_method(self, path, sign, kwargs):
        uid = kwargs.pop('uid')
        kwargs.pop('location', None)
        kwargs.pop('conn', None)
        if sign == USER_SIGN:
            self.send(dict(path='.'.join(path), kwargs=kwargs))
        elif sign == INTERNAL_SIGN:
            conn = self._connman.get_connection(uid)
            if conn is None:
                return
            path_prefix = list(self._config.outer_server.
                            client_location_handler_path.split('.'))
            path = path_prefix + path
            conn.send(dict(path='.'.join(path), kwargs=kwargs))


