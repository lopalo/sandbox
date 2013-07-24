import argparse
import logging
import random
import yaml

from tornado.ioloop import IOLoop
from tornado.gen import coroutine
from sulaco.utils import Config, ColorUTCFormatter
from zmq.eventloop.ioloop import install
from sulaco.utils.db import check_db
from sulaco.location_server.gateway import Gateway as BasicGateway

from utils.debugging import set_debug_mode
from location.root import Root
from location.db import (LocationRedisPool,
    QUEUE_WORK_IDENTS_KEY, WORK_IDENTS_KEY)
from location.work import work_handlers, process_ticks


logger = logging.getLogger(__name__)


@coroutine
def prepare_db(loc_config, ioloop):
    try:
        dbc = loc_config.db
        db = LocationRedisPool(host=dbc.host, port=dbc.port, db=dbc.db)
        yield from check_db(dbc.name, db)
        yield from db.load_scripts()
        # recreate active work queue
        yield db.delete(QUEUE_WORK_IDENTS_KEY)
        yield db.zunionstore(QUEUE_WORK_IDENTS_KEY, WORK_IDENTS_KEY)
    finally:
        ioloop.stop()
    return db


def load_work_handlers(path, db, gateway):
    with open(path, 'rb') as f:
        dct = yaml.safe_load(f)
        for k, v in dct.items():
            cls = work_handlers[v.pop('type')]
            v['ident'] = k
            handler = cls(**v)
            handler.setup(db, gateway)
            yield k, handler


class Gateway(BasicGateway):

    def private_message(self, uid, msg):
        msg['kwargs']['_update_in_loc'] = False
        super().private_message(uid, msg)


def main(options):
    install()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(ColorUTCFormatter())
    logger.addHandler(handler)

    loc_config = Config.load_yaml(options.location_config)
    random.seed(0)

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

    wh_conf = loc_config.work_handlers
    work_handlers = dict(load_work_handlers(wh_conf.path, db, gateway))
    root.work_handlers = work_handlers
    for _ in range(wh_conf.tick_processors):
        process_ticks(db, work_handlers, wh_conf.works_per_step)

    if options.debug:
        set_debug_mode()

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

