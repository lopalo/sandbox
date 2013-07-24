import msgpack

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

    @message_receiver(INTERNAL_SIGN)
    def enter(self, **kwargs):
        connman = self._connman
        user = self._user
        loc_conn = self._loc_input
        conn = connman.get_connection(user.uid)
        if conn is None:
            return
        prev_loc = user.location
        if user.location is not None and user.location != self._ident:
            connman.remove_user_from_location(user.location, user.uid)
        user.location = self._ident
        connman.add_user_to_location(self._ident, user.uid)
        loc_conn.s.enter(user=user.location_view(), prev_loc=prev_loc)

    @message_receiver(INTERNAL_SIGN)
    def update_field(self, field, value, **kwargs):
        #TODO: use difference to avoid of state rewriting
        setattr(self._user, field, value)

    def proxy_method(self, path, sign, kwargs):
        uid = kwargs.pop('uid')
        kwargs.pop('location', None)
        kwargs.pop('conn', None)
        kwargs.pop('_update_in_loc', None)
        if sign == USER_SIGN:
            self._loc_input.send(dict(path='.'.join(path), kwargs=kwargs),
                                                            sign=USER_SIGN)
        elif sign == INTERNAL_SIGN:
            conn = self._connman.get_connection(uid)
            if conn is None:
                return
            path_prefix = list(self._config.outer_server.
                            client_location_handler_path.split('.'))
            path = path_prefix + path
            conn.send(dict(path='.'.join(path), kwargs=kwargs))


