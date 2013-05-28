from unittest.mock import ANY
from tests.tools import FuncTestCase


class TestAuth(FuncTestCase):

    def runTest(self):
        c1 = self.client()
        c1.connect(7010)
        c1.s.register(username='mega_user', password='111')
        info = c1.recv(path_prefix='user.basic_info')['kwargs']['data']
        self.assertEqual(dict(name='mega_user', uid=ANY), info)
        c1.close()
        c2 = self.client()
        c2.connect(7010)
        c2.s.register(username='mega_user', password='111')
        self.assertEqual({'text': 'username exists'},
                            c2.recv(path_prefix='auth.error')['kwargs'])
        c2.s.sign_in(username='mega_user1', password='111')
        self.assertEqual({'text': 'unknown username'},
                            c2.recv(path_prefix='auth.error')['kwargs'])
        c2.s.sign_in(username='mega_user', password='222')
        self.assertEqual({'text': 'wrong username or password'},
                            c2.recv(path_prefix='auth.error')['kwargs'])
        c2.s.sign_in(username='mega_user', password='111')
        self.assertEqual(info,
                c2.recv(path_prefix='user.basic_info')['kwargs']['data'])

