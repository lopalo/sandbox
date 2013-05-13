import argparse
import logging
from random import choice

from tornado.ioloop import IOLoop
from sulaco.outer_server.tcp_server import TCPServer, SimpleProtocol
from sulaco.outer_server.connection_manager import (
    DistributedConnectionManager,
    ConnectionHandler, LocationMixin)
from sulaco.utils.receiver import (
    message_receiver, message_router, LoopbackMixin,
    ProxyMixin, USER_SIGN, INTERNAL_USER_SIGN, INTERNAL_SIGN)
from sulaco.utils import Config, UTCFormatter
from sulaco.utils.zmq import install
from sulaco.outer_server.message_manager import MessageManager
from sulaco.outer_server.message_manager import Root as ABCRoot


logger = logging.getLogger(__name__)


class Root(ABCRoot, LoopbackMixin):

    def __init__(self, config, connman, msgman):
        super().__init__()
        self._config = config
        self._connman = connman
        self._msgman = msgman
        #TODO: generate server id

    @message_receiver()
    def sign_id(self, username, conn, loc=None, **kwargs):
        #TODO: Save server id in user and check it all time when
        #      user will be loaded from db.
        #      Disconnect if server id is wrong.
        pass

    def location_added(self, loc_id):
        pass

    def location_removed(self, loc_id):
        pass


class Protocol(ConnectionHandler, SimpleProtocol):
    pass


class ConnManager(LocationMixin, DistributedConnectionManager):
    pass


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(UTCFormatter())
    logger.addHandler(handler)

    config = Config.load_yaml(options.config)
    msgman = MessageManager(config)
    msgman.connect()
    connman = ConnManager(pub_socket=msgman.pub_to_broker,
                          sub_socket=msgman.sub_to_broker,
                          locations_sub_socket=msgman.sub_to_locs)
    root = Root(config, connman, msgman)
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
