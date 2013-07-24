import ujson

from itertools import chain

from sulaco.utils.db import (
    RedisClient, RedisPool,
    RedisScript, RedisScriptsContainer)
from sulaco.utils import get_pairs


USER_IDENTS_KEY = '_user_idents_'
WORK_IDENTS_KEY = '_work_idents_'
QUEUE_WORK_IDENTS_KEY = '_queue_work_idents_'


def unpack_hash(key_values):
    return {k.decode('utf-8'): ujson.loads(v, precise_float=True)
                                for k, v in get_pairs(key_values)}

def pack_hash(dct, to_dict=False):
    if to_dict:
        # redis.hmset processes dict correctly
        return {k: ujson.dumps(v) for k, v in dct.items()}
    return list(chain(*[(k, ujson.dumps(v)) for k, v in dct.items()]))



class Id(str):
    prefix = None # define in subclasses

    def __repr__(self):
        return self.__str__()

    def encode(self, *args, **kwargs):
        return self.__str__().encode(*args, **kwargs)

    def __str__(self):
        return self.prefix + self

    @property
    def original(self):
        return self.strip()


class UserId(Id):
    prefix = 'user:'


class WorkId(Id):
    prefix = 'work:'


class LocationRedisPool(RedisScriptsContainer, RedisPool):
    client_cls = RedisClient
    #TODO: test scripts

    get_all_objects = RedisScript("""
        local ids = redis.call('SMEMBERS', KEYS[1])
        local objects = {}
        for n, id in pairs(ids) do
            table.insert(objects, redis.call('HGETALL', id))
        end
        return objects
    """)

    # updates hash if key exists
    update_hash_exists = RedisScript("""
        local exists = redis.call('EXISTS', KEYS[1])
        if exists ~= 1 then
            return false
        end
        local cmd = ARGV
        table.insert(cmd, 1, KEYS[1])
        table.insert(cmd, 1, 'HMSET')
        redis.call(unpack(cmd))
        return true
    """)

    ### work section ###

    # returns info of active works
    get_work_list = RedisScript("""
        local wids = redis.call('ZRANGEBYSCORE', '{queue_work_idents}',
                                '-inf', KEYS[1], 'LIMIT', 0, KEYS[2])
        local rem_cmd = {{'ZREM', '{queue_work_idents}'}}
        local works = {{}}
        for n, wid in pairs(wids) do
            table.insert(rem_cmd, wid)
            table.insert(works, redis.call('HGETALL', wid))
        end
        if table.getn(rem_cmd) > 2 then
            redis.call(unpack(rem_cmd))
        end
        return works
    """.format(queue_work_idents=QUEUE_WORK_IDENTS_KEY))

    cancel_work = RedisScript("""
        redis.call('ZREM', '{works_idents}', KEYS[1])
        redis.call('ZREM', '{queue_work_idents}', KEYS[1])
        redis.call('DEL', KEYS[1])
        redis.status_reply('OK')
    """.format(works_idents=WORK_IDENTS_KEY,
               queue_work_idents=QUEUE_WORK_IDENTS_KEY))

    # continue work if it is still active
    continue_work = RedisScript("""
        if not redis.call('ZSCORE', '{works_idents}', KEYS[1]) then
            return
        end
        redis.call('ZADD', '{works_idents}', KEYS[2], KEYS[1])
        redis.call('ZADD', '{queue_work_idents}', KEYS[2], KEYS[1])
        redis.call('HSET', KEYS[1], 'last_ts', KEYS[3])
        redis.status_reply('OK')
    """.format(works_idents=WORK_IDENTS_KEY,
               queue_work_idents=QUEUE_WORK_IDENTS_KEY))

    start_work = RedisScript("""
        redis.call('ZADD', '{works_idents}', KEYS[2], KEYS[1])
        redis.call('ZADD', '{queue_work_idents}', KEYS[2], KEYS[1])
        local cmd = ARGV
        table.insert(cmd, 1, KEYS[1])
        table.insert(cmd, 1, 'HMSET')
        redis.call(unpack(cmd))
        redis.status_reply('OK')
    """.format(works_idents=WORK_IDENTS_KEY,
               queue_work_idents=QUEUE_WORK_IDENTS_KEY))

