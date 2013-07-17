import msgpack
from tornado.testing import gen_test
from tests.tools import FuncTestCase


class TestUserFinilize(FuncTestCase):

    def runTest(self):
        c = self.client()
        c.register('username', port=7010)
        c.flush()
        c.s.user.change_field(name='name', value='barmaley')
        info = c.recv(path_prefix='user.basic_info')['kwargs']['data']
        self.assertEqual('barmaley', info['name'])
        res = c.recv(path_prefix='location.user_updated')['kwargs']['user']
        self.assertEqual('barmaley', res['name'])
        res = self.find_in_shards(info['uid'], 'basic', cmd='hget')
        res = msgpack.loads(res, encoding='utf-8')
        self.assertEqual('barmaley', res['name'])
        self.redis('select', self.main_loc_config.db.db)
        res = self.redis('hget', 'user:' + info['uid'], 'name')
        self.assertEqual(b'barmaley', res)
