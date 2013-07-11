import argparse
import logging

from tornado.ioloop import IOLoop
from tornado.gen import coroutine
from sulaco.utils import Config, ColorUTCFormatter
from zmq.eventloop.ioloop import install
from sulaco.utils.db import check_db
from sulaco.location_server.gateway import Gateway

from location.root import Root
from location.db import LocationRedisPool


logger = logging.getLogger(__name__)


@coroutine
def prepare_db(loc_config, ioloop):
    try:
        dbc = loc_config.db
        db = LocationRedisPool(host=dbc.host, port=dbc.port, db=dbc.db)
        yield from check_db(dbc.name, db)
        yield from db.get_client().load_scripts()
    finally:
        ioloop.stop()
    return db


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(ColorUTCFormatter())
    logger.addHandler(handler)

    loc_config = Config.load_yaml(options.location_config)

    ioloop = IOLoop.instance()
    db_fut = prepare_db(loc_config, ioloop)
    ioloop.start()

    db = db_fut.result()
    config = Config.load_yaml(options.config)
    gateway = Gateway(config, loc_config.ident)
    root = Root(gateway, loc_config, db)
    gateway.setup(root)
    connected = gateway.connect(loc_config.pub_address,
                                loc_config.pull_address)
    if not connected:
        return
    gateway.start(ioloop) # runs ioloop again

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
