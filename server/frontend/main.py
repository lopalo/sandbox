import argparse
import logging

from tornado.ioloop import IOLoop
from sulaco.outer_server.tcp_server import TCPServer, SimpleProtocol
from sulaco.outer_server.connection_manager import (
    DistributedConnectionManager,
    ConnectionHandler, LocationConnectionManager)
from sulaco.utils import Config, UTCFormatter
from sulaco.utils.zmq import install
from sulaco.outer_server.message_manager import (
    MessageManager, LocationMessageManager)
from toredis.client import ClientPool as BasicRedisPool
from toredis.commands_future import RedisCommandsFutureMixin
from toredis.nodes import RedisNodes

from frontend.root import Root

logger = logging.getLogger(__name__)


class RedisPool(RedisCommandsFutureMixin, BasicRedisPool):
    pass


class Protocol(ConnectionHandler, SimpleProtocol):
    pass


class ConnManager(LocationConnectionManager, DistributedConnectionManager):
    pass


class MsgManager(MessageManager, LocationMessageManager):
    pass


def setup_dbs(config):
    def check_result(future):
        try:
            future.result()
        except Exception:
            logger.exception("DB check is failed")
            IOLoop.instance().stop()

    nodes = RedisNodes(nodes=config.outer_server.db_nodes)
    nodes.check_nodes().add_done_callback(check_result)

    conf = config.outer_server.name_db
    name_db = RedisPool(host=conf.host, port=conf.port, db=conf.db)
    name_db.setnx('db_name', conf.name).add_done_callback(check_result)

    return dict(nodes=nodes,
                name_db=name_db)


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(UTCFormatter())
    logger.addHandler(handler)

    config = Config.load_yaml(options.config)
    msgman = MsgManager(config)
    msgman.connect()
    connman = ConnManager(pub_socket=msgman.pub_to_broker,
                          sub_socket=msgman.sub_to_broker,
                          locations_sub_socket=msgman.sub_to_locs)
    dbs = setup_dbs(config)
    root = Root(config, connman, msgman, dbs)
    msgman.setup(connman, root)
    server = TCPServer()
    server.setup(Protocol, connman, root, options.max_conn)
    server.listen(options.port)
    IOLoop.instance().start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='run on the given port',
                        action='store', dest='port', type=int, required=True)
    parser.add_argument('-mc', '--max-conn', help='max connections on server',
                        action='store', dest='max_conn', type=int)
    parser.add_argument('-c', '--config', action='store', dest='config',
                        help='path to config file', type=str, required=True)
    parser.add_argument('-d', '--debug', action='store_true',
                        dest='debug', help='Set debug level of logging')
    options = parser.parse_args()
    main(options)
