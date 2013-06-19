from sulaco.utils.db import (
    RedisClient, RedisPool,
    RedisScript, RedisScriptsContainer)


user_idents_key = 'user_idents'


class UserId(str):

    def __repr__(self):
        return 'user:' + self


class LocationRedis(RedisScriptsContainer, RedisClient):

    get_all_users = RedisScript("""
        local uids = redis.call('SMEMBERS', '{user_idents}')
        local users = {{}}
        for n, uid in pairs(uids) do
            table.insert(users, redis.call('HGETALL', uid))
        end
        return users
    """.format(user_idents=user_idents_key))


class LocationRedisPool(RedisPool):
    client_cls = LocationRedis


