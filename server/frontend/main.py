import argparse
import logging

from tornado.ioloop import IOLoop
from tornado.gen import coroutine
from sulaco.outer_server.tcp_server import TCPServer, SimpleProtocol
from sulaco.outer_server.connection_manager import (
    DistributedConnectionManager,
    ConnectionHandler, LocationConnectionManager)
from sulaco.utils import Config, ColorUTCFormatter
from zmq.eventloop.ioloop import install
from sulaco.outer_server.message_manager import (
    MessageManager, LocationMessageManager)
from sulaco.utils.db import RedisPool, RedisNodes, check_db

from frontend.root import Root
from utils.debugging import set_debug_mode


logger = logging.getLogger(__name__)


class Protocol(ConnectionHandler, SimpleProtocol):
    pass


class ConnManager(LocationConnectionManager, DistributedConnectionManager):
    pass


class MsgManager(MessageManager, LocationMessageManager):
    pass


@coroutine
def prepare_dbs(config, on_ready):
    try:
        nodes = RedisNodes(nodes=config.outer_server.db_nodes)
        for info, cli in nodes.nodes:
            yield from check_db(info['name'], cli)

        conf = config.outer_server.name_db
        name_db = RedisPool(host=conf.host, port=conf.port, db=conf.db)
        yield from check_db(conf.name, name_db)
    except Exception:
        IOLoop.instance().stop()
        raise
    else:
        on_ready(nodes=nodes, name_db=name_db)


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(ColorUTCFormatter())
    logger.addHandler(handler)

    config = Config.load_yaml(options.config)

    def on_db_ready(**dbs):
        msgman = MsgManager(config)
        msgman.connect()
        connman = ConnManager(pub_socket=msgman.pub_to_broker,
                              sub_socket=msgman.sub_to_broker,
                              locations_sub_socket=msgman.sub_to_locs)
        game_config = Config.load_yaml(options.game_config)
        root = Root(config, game_config, connman, msgman, dbs)
        msgman.setup(connman, root)
        server = TCPServer()
        server.setup(Protocol, connman, root, options.max_conn)
        server.listen(options.port)

    prepare_dbs(config, on_db_ready)
    if options.debug:
        set_debug_mode()
    IOLoop.instance().start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='run on the given port',
                        action='store', dest='port', type=int, required=True)
    parser.add_argument('-mc', '--max-conn', help='max connections on server',
                        action='store', dest='max_conn', type=int)
    parser.add_argument('-c', '--config', action='store', dest='config',
                        help='path to config file', type=str, required=True)
    parser.add_argument('-gc', '--game-config', action='store',
                        dest='game_config', help='path to config file',
                        type=str, required=True)
    parser.add_argument('-d', '--debug', action='store_true',
                        dest='debug', help='set debug level of logging')
    options = parser.parse_args()
    main(options)
