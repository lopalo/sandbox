from unittest.mock import ANY
from tests.tools import FuncTestCase


class TestWrongFrontendId(FuncTestCase):
    maxDiff = None

    def runTest(self):
        c = self.client()
        c.register('user', port=7010)
        c.s.user.get_basic_info()
        ret = c.recv(path_prefix='user.basic_info')['kwargs']['data']
        self.assertEqual(0, ret['stones'])
        c.s.location.increase_stones(duration=5, amount=15)
        ret = c.recv(path_prefix='location.new_work')['kwargs']
        self.assertEqual({'finish_ts': ANY,
                          'finish_val': 15,
                          'ident': ANY,
                          'info': None,
                          'last_ts': ANY,
                          'object_id': 'user:' + c.uid,
                          'start_ts': ANY,
                          'start_val': 0,
                          'work_handler': 'incr_stones'}, ret['work'])
        ret = c.recv(path_prefix='user.basic_info')['kwargs']['data']
        self.assertEqual(15, ret['stones'])
