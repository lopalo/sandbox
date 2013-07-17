from sulaco.utils.db import (
    RedisClient, RedisPool,
    RedisScript, RedisScriptsContainer)


user_idents_key = 'user_idents'


class Id(str):

    def __repr__(self):
        return self.__str__()

    def encode(self, *args, **kwargs):
        return self.__str__().encode(*args, **kwargs)

    def __str__(self):
        raise NotImplemented


class UserId(Id):

    def __str__(self):
        return 'user:' + self


class LocationRedisPool(RedisScriptsContainer, RedisPool):
    client_cls = RedisClient

    get_all_users = RedisScript("""
        local uids = redis.call('SMEMBERS', '{user_idents}')
        local users = {{}}
        for n, uid in pairs(uids) do
            table.insert(users, redis.call('HGETALL', uid))
        end
        return users
    """.format(user_idents=user_idents_key))

    # updates hash if key exists
    update_hash_exists = RedisScript("""
        local exists = redis.call('EXISTS', KEYS[1])
        if exists ~= 1 then
            return false
        end
        table.insert(ARGV, 1, KEYS[1])
        table.insert(ARGV, 1, 'HMSET')
        redis.call(unpack(ARGV))
        return true
    """)


