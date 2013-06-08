import hashlib
import msgpack

from steward import Component, Field

from sulaco.utils.receiver import message_receiver, USER_SIGN


class User(Component):
    frontend_id = Field()
    uid = Field()
    name = Field()
    location = Field()
    password_hash = Field()

    _need_save = False

    @property
    def need_save(self):
        return self._need_save

    def mark_save(self):
        self._need_save = True

    @message_receiver(USER_SIGN)
    def get_basic_info(self, conn, **kwargs):
        conn.s.user.basic_info(data=self.json_view())

    @staticmethod
    def generate_password_hash(password):
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @classmethod
    def load(cls, uid, db):
        packed = yield db[uid].hget(uid, 'basic')
        return cls(**msgpack.loads(packed, encoding='utf-8'))

    def save(self, db):
        yield db[self.uid].hset(self.uid, 'basic',
                    msgpack.dumps(self.as_plain()))
        self._need_save = False

    def json_view(self):
        return {'uid': self.uid,
                'name': self.name}

