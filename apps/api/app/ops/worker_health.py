"""Health check for the shared beat/broker/worker pipeline, not an HTTP server."""
import redis
from ..config import settings

client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
try:
    healthy = bool(client.get('safarios:worker-heartbeat'))
except redis.RedisError:
    healthy = False
raise SystemExit(0 if healthy else 1)
