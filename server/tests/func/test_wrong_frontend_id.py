from tests.tools import FuncTestCase

from sulaco.tests.tools import ConnectionClosed


class TestWrongFrontendId(FuncTestCase):

    def runTest(self):
        c1 = self.client()
        c1.register('user', port=7010)
        c1.s.user.get_basic_info()
        c1.recv(path_prefix='user.basic_info')
        c2 = self.client()
        c2.connect(7011)
        c2.s.sign_in(username='user', password='')
        c2.recv(path_prefix='user.basic_info')
        c1.s.user.get_basic_info()
        with self.assertRaises(ConnectionClosed):
            c1.recv(1, path_prefix='user.basic_info')
        c2.flush()
        c2.s.user.get_basic_info()
        c2.recv(path_prefix='user.basic_info')


