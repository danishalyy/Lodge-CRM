"""Atomic distributed admission; Redis loss disables AI, never the core CRM."""

from contextlib import contextmanager
import secrets, time
import redis
from fastapi import HTTPException
from ..config import settings

ADMIT = """
local u=redis.call('INCR',KEYS[1]); if u==1 then redis.call('EXPIRE',KEYS[1],60) end
local l=redis.call('INCR',KEYS[2]); if l==1 then redis.call('EXPIRE',KEYS[2],60) end
if u>tonumber(ARGV[4]) or l>tonumber(ARGV[5]) then return 0 end
for i=3,4 do redis.call('ZREMRANGEBYSCORE',KEYS[i],'-inf',ARGV[1]) end
if redis.call('ZCARD',KEYS[3])>=tonumber(ARGV[6]) or redis.call('ZCARD',KEYS[4])>=tonumber(ARGV[7]) then return 0 end
for i=3,4 do redis.call('ZADD',KEYS[i],ARGV[2],ARGV[3]);redis.call('EXPIRE',KEYS[i],tonumber(ARGV[8])) end
return 1
"""


@contextmanager
def admission(user_id, lodge_id):
    client = redis.Redis.from_url(
        settings.redis_url, socket_connect_timeout=2, socket_timeout=2
    )
    token = secrets.token_hex(16)
    now = time.time()
    ttl = int(settings.ai_request_timeout * settings.ai_max_rounds + 30)
    keys = [
        f"ai:rate:user:{user_id}",
        f"ai:rate:lodge:{lodge_id}",
        f"ai:active:user:{user_id}",
        f"ai:active:lodge:{lodge_id}",
    ]
    try:
        ok = client.eval(
            ADMIT,
            4,
            *keys,
            now,
            now + ttl,
            token,
            settings.ai_user_requests_per_minute,
            settings.ai_lodge_requests_per_minute,
            1,
            settings.ai_lodge_concurrency,
            ttl,
        )
    except redis.RedisError:
        raise HTTPException(503, "AI admission service is unavailable") from None
    if not ok:
        raise HTTPException(
            429, "AI is busy. Please try again shortly", headers={"Retry-After": "60"}
        )
    try:
        yield
    finally:
        try:
            client.zrem(keys[2], token)
            client.zrem(keys[3], token)
        except redis.RedisError:
            pass  # Leases expire independently; no open-ended permit.
        client.close()
