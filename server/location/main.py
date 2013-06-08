import argparse
import logging

from tornado.ioloop import IOLoop
from sulaco.utils import Config, UTCFormatter
from sulaco.utils.zmq import install
from sulaco.utils.db import RedisPool, check_db
from sulaco.location_server.gateway import Gateway

from location.root import Root


logger = logging.getLogger(__name__)


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(UTCFormatter())
    logger.addHandler(handler)

    loc_config = Config.load_yaml(options.location_config)
    dbc = loc_config.db
    db = RedisPool(host=dbc.host, port=dbc.port, db=dbc.db)
    check_db(dbc.name, db, IOLoop.instance())

    config = Config.load_yaml(options.config)
    gateway = Gateway(config, loc_config.ident)
    root = Root(gateway, loc_config, db)
    gateway.setup(root)
    connected = gateway.connect(loc_config.pub_address,
                                loc_config.pull_address)
    if not connected:
        return
    gateway.start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-lc', '--location-config', action='store',
                        dest='location_config', help='path to config file',
                        type=str, required=True)
    parser.add_argument('-c', '--config', action='store', dest='config',
                        help='path to config file', type=str, required=True)
    parser.add_argument('-d', '--debug', action='store_true',
                        dest='debug', help='set debug level of logging')
    options = parser.parse_args()
    main(options)
