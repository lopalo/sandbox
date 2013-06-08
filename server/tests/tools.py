import subprocess
import logging
import time

from tornado import testing

from sulaco.tests.tools import BlockingClient
from sulaco.utils import ColorUTCFormatter, Config

from sulaco.utils.db import RedisClient


class Client(BlockingClient):
    cmds_to_discard = ['user.basic_info']

    def register(self, name, password='', discard_cmds=True, port=7010):
        self.connect(port)
        self.s.register(username=name, password=password)
        if discard_cmds:
            for cmd in self.cmds_to_discard:
                self.recv(path_prefix=cmd)


class FuncTestCase(testing.AsyncTestCase):
    debug = True # set DEBUG level of logging

    global_config = 'tests/configs/global.yaml'
    game_config = 'tests/configs/game.yaml'
    main_loc_config = 'tests/configs/location_main.yaml'
    second_loc_config = 'tests/configs/location_second.yaml'

    def setUp(self):
        super().setUp()
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(ColorUTCFormatter())
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
        redis.select(conf.outer_server.name_db.db, callback=self.stop)
        self.wait()
        redis.flushdb(callback=self.stop)
        self.wait()
        for pth in (self.main_loc_config, self.second_loc_config):
            lconf = Config.load_yaml(pth)
            redis.select(lconf.db.db, callback=self.stop)
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
                 '-gc', self.game_config,
                 '--debug'],
                ['python',
                 'frontend/main.py',
                 '-p', '7011',
                 '-c', self.global_config,
                 '-gc', self.game_config,
                 '--debug'],
                ['python',
                 'location/main.py',
                 '-c', self.global_config,
                 '-lc', self.main_loc_config,
                 '--debug'],
                ['python',
                 'location/main.py',
                 '-c', self.global_config,
                 '-lc', self.second_loc_config,
                 '--debug'])
        self._services = [subprocess.Popen(cmd) for cmd in cmds]
        time.sleep(0.7)

    def tearDown(self):
        for s in self._services:
            s.terminate()
        for c in self._clients:
            c.close()
        time.sleep(0.1)

    def client(self):
        c = Client(ioloop=self.io_loop)
        self._clients.append(c)
        return c
