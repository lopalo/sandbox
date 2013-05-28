import subprocess
import logging
import time

from tornado import testing

from sulaco.redis import Client as RedisClient
from sulaco.tests.tools import BlockingClient
from sulaco.utils import UTCFormatter, Config


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
                 'sulaco/sulaco/outer_server/message_broker.py',
                 '-c', self.global_config],
                ['python',
                 'sulaco/sulaco/location_server/location_manager.py',
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
        c = BlockingClient(ioloop=self.io_loop)
        self._clients.append(c)
        return c
