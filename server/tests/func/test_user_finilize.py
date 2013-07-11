from tests.tools import FuncTestCase


class TestUserFinilize(FuncTestCase):

    def runTest(self):
        c = self.client()
        c.register('username', port=7010)
        c.flush()
        self.flush_log_buffer()
        c.s.user.change_field(name='name', value='barmaley')
        info = c.recv(path_prefix='user.basic_info')['kwargs']['data']
        self.assertEqual('barmaley', info['name'])
        self.wait_log_message(r'User uid:\w+ saved', 10)
        match = self.wait_log_message(
            r"sulaco.location_server.gateway: "
             "Received message:.*'path': 'update_user'.*", 10)
        self.assertIn("'name': 'barmaley'", match.string)
