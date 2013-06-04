import subprocess
import logging
import time

from tornado import testing

from toredis.client import Client as BasicRedisClient
from toredis.commands_future import RedisCommandsFutureMixin
from sulaco.tests.tools import BlockingClient
from sulaco.utils import UTCFormatter, Config


class Client(BlockingClient):
    cmds_to_discard = ['user.basic_info']

    def register(self, name, password='', discard_cmds=True, port=7010):
        self.connect(port)
        self.s.register(username=name, password=password)
        if discard_cmds:
            for cmd in self.cmds_to_discard:
                self.recv(path_prefix=cmd)

class RedisClient(RedisCommandsFutureMixin, BasicRedisClient):
    pass


class FuncTestCase(testing.AsyncTestCase):
    debug = True # set DEBUG level of logging

    global_config = 'tests/configs/global.yaml'

    def setUp(self):
        super().setUp()
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(UTCFormatter())
        logger.addHandler(handler)

        self._clients = []

        self.redis = redis = RedisClient(io_loop=self.io_loop)
        self.redis.connect()
        conf = Config.load_yaml(self.global_config)
        for n in conf.outer_server.db_nodes:
            redis.select(n['db'], callback=self.stop)
            self.wait()
            redis.flushdb(callback=self.stop)
            self.wait()
        redis.select(conf.outer_server.name_db['db'], callback=self.stop)
        self.wait()
        redis.flushdb(callback=self.stop)
        self.wait()

        cmds = (['python',
                 'sulaco/outer_server/message_broker.py',
                 '-c', self.global_config],
                ['python',
                 'sulaco/location_server/location_manager.py',
                 '-c', self.global_config],
                ['python',
                 'frontend/main.py',
                 '-p', '7010',
                 '-c', self.global_config,
                 '--debug'],
                ['python',
                 'frontend/main.py',
                 '-p', '7011',
                 '-c', self.global_config,
                 '--debug'],
                ['python',
                 'location/main.py',
                 '-pub', 'ipc://run/testing/loc_1_pub',
                 '-pull', 'ipc://run/testing/loc_1_pull',
                 '-ident', 'loc_1',
                 '-c', self.global_config,
                 '--debug'],
                ['python',
                 'location/main.py',
                 '-pub', 'ipc://run/testing/loc_2_pub',
                 '-pull', 'ipc://run/testing/loc_2_pull',
                 '-ident', 'loc_2',
                 '-c', self.global_config,
                 '--debug'])
        self._services = [subprocess.Popen(cmd) for cmd in cmds]
        time.sleep(0.7)

    def tearDown(self):
        for s in self._services:
            s.terminate()
        for c in self._clients:
            c.close()

    def client(self):
        c = Client(ioloop=self.io_loop)
        self._clients.append(c)
        return c
