import subprocess
import logging
import time
import os
import fcntl
import re

from threading import Thread
from collections import deque
from tornado import testing

from sulaco.tests.tools import BlockingClient, TimeoutError
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
    read_output = False # read in separate thread output of child processes

    global_config_path = 'tests/configs/global.yaml'
    game_config_path = 'tests/configs/game.yaml'
    main_loc_config_path = 'tests/configs/location_main.yaml'
    second_loc_config_path = 'tests/configs/location_second.yaml'

    def setUp(self):
        super().setUp()
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(ColorUTCFormatter())
        logger.addHandler(handler)

        self._clients = []

        self._redis_cli = RedisClient(io_loop=self.io_loop)
        self._redis_cli.connect()
        redis = self.redis
        conf = self.global_config = Config.load_yaml(self.global_config_path)
        self.main_loc_config = Config.load_yaml(self.main_loc_config_path)
        self.second_loc_config = Config.load_yaml(self.second_loc_config_path)
        for n in conf.outer_server.db_nodes:
            redis('select', n['db'])
            redis('flushdb')
        redis('select', conf.outer_server.name_db.db)
        redis('flushdb')
        redis('select', self.main_loc_config.db.db)
        redis('flushdb')
        redis('select', self.second_loc_config.db.db)
        redis('flushdb')

        cmds = (['python',
                 'sulaco/outer_server/message_broker.py',
                 '-c', self.global_config_path],
                ['python',
                 'sulaco/location_server/location_manager.py',
                 '-c', self.global_config_path],
                ['python',
                 'frontend/main.py',
                 '-p', '7010',
                 '-c', self.global_config_path,
                 '-gc', self.game_config_path,
                 '--debug'],
                ['python',
                 'frontend/main.py',
                 '-p', '7011',
                 '-c', self.global_config_path,
                 '-gc', self.game_config_path,
                 '--debug'],
                ['python',
                 'location/main.py',
                 '-c', self.global_config_path,
                 '-lc', self.main_loc_config_path,
                 '--debug'],
                ['python',
                 'location/main.py',
                 '-c', self.global_config_path,
                 '-lc', self.second_loc_config_path,
                 '--debug'])
        if self.read_output:
            stdout = subprocess.PIPE
            stderr = subprocess.STDOUT
        else:
            stdout = None
            stderr = None
        self._services = [subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr) for cmd in cmds]
        self._start_log_thread()
        time.sleep(0.7)

    def _start_log_thread(self):
        #TODO: change to zmq logging
        if not self.read_output:
            return
        self._stop_log_thread = False
        self._log_buffer = deque()
        for serv in self._services:
            fcntl.fcntl(serv.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        def _read_func():
            while not self._stop_log_thread:
                for serv in self._services:
                    try:
                        while True:
                            line = serv.stdout.readline()
                            if line:
                                line = line[:-1].decode('utf-8')
                                print(line)
                                self._log_buffer.append(line)
                            else:
                                break
                    except IOError:
                        pass
        Thread(target=_read_func).start()

    def wait_log_message(self, pattern, seconds=5):
        start = self.io_loop.time()
        while self.io_loop.time() - start < seconds:
            while self._log_buffer:
                line = self._log_buffer.popleft()
                match = re.search(pattern, line)
                if match is not None:
                    return match
        msg = "Pattern '{}' is not found in {} seconds".format(pattern,
                                                               seconds)
        raise TimeoutError(msg)

    def flush_log_buffer(self):
        self._log_buffer = deque()

    def tearDown(self):
        #TODO: speed up
        self._stop_log_thread = True
        for s in self._services:
            s.terminate()
            s.wait()
        for c in self._clients:
            c.close()

    def client(self):
        c = Client(ioloop=self.io_loop)
        self._clients.append(c)
        return c

    def redis(self, cmd, *args):
        getattr(self._redis_cli, cmd.lower())(*args, callback=self.stop)
        return self.wait()

    def find_in_shards(self, *args, cmd='get'):
        for n in self.global_config.outer_server.db_nodes:
            self.redis('select', n['db'])
            ret = self.redis(cmd, *args)
            if ret is not None:
                return ret

