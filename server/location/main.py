import argparse
import logging

from sulaco.utils import Config, UTCFormatter
from sulaco.utils.zmq import install
from sulaco.utils.receiver import message_receiver, INTERNAL_SIGN
from sulaco.location_server.gateway import Gateway


logger = logging.getLogger(__name__)


class Root(object):

    def __init__(self, gateway, ident, config):
        self._gateway = gateway
        self._config = config
        self._ident = ident


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(UTCFormatter())
    logger.addHandler(handler)

    config = Config.load_yaml(options.config)
    gateway = Gateway(config, options.ident)
    root = Root(gateway, options.ident, config)
    gateway.setup(root)
    connected = gateway.connect(options.pub_address, options.pull_address)
    if not connected:
        return
    gateway.start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-pub', '--pub-address',
                        help='address of zmq pub socket', action='store',
                        dest='pub_address', type=str, required=True)
    parser.add_argument('-pull', '--pull-address',
                        help='address of zmq pull socket', action='store',
                        dest='pull_address', type=str, required=True)
    parser.add_argument('-ident', '--ident',
                        help='ident of location that will be processing',
                        action='store', dest='ident', type=str, required=True)
    parser.add_argument('-c', '--config', action='store', dest='config',
                        help='path to config file', type=str, required=True)
    parser.add_argument('-d', '--debug', action='store_true',
                        dest='debug', help='Set debug level of logging')
    options = parser.parse_args()
    main(options)
