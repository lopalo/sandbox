import hashlib
import msgpack

from steward import Component, Field


class User(Component):
    frontend_id = Field()
    uid = Field()
    name = Field()
    password_hash = Field()
    #TODO: check if wrong frontend_id

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

    def json_view(self):
        #TODO: without password and frontend_id
        pass

