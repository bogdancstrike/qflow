"""Sliding-window rate limiter using Redis.

Enforces per-IP rate limiting on task creation endpoints.
Works across multiple replicas since Redis is the shared counter store.
"""

import os
import time

import redis

from framework.commons.logger import logger
from src.config import Config

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "100"))
WINDOW_SEC = 60  # 1 minute sliding window

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=int(Config.REDIS_PORT),
            db=int(Config.REDIS_DB),
            socket_timeout=float(Config.REDIS_SOCKET_TIMEOUT),
            socket_connect_timeout=float(Config.REDIS_CONNECT_TIMEOUT),
            decode_responses=True,
        )
    return _redis_client


def get_client_ip(request) -> str:
    """Extract client IP, respecting X-Forwarded-For if present."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def check_rate_limit(request) -> tuple:
    """Check if the request exceeds the rate limit.

    Returns:
        (allowed, retry_after_seconds)
        allowed=True means the request can proceed.
        If allowed=False, retry_after is the number of seconds until the window resets.
    """
    if RATE_LIMIT_RPM <= 0:
        return True, 0

    client_ip = get_client_ip(request)
    key = f"ratelimit:{client_ip}"
    now = time.time()
    window_start = now - WINDOW_SEC

    try:
        r = _get_redis()
        pipe = r.pipeline()

        # Remove entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count remaining entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {f"{now}": now})
        # Set TTL on the key
        pipe.expire(key, WINDOW_SEC + 1)

        results = pipe.execute()
        current_count = results[1]

        if current_count >= RATE_LIMIT_RPM:
            # Get the oldest entry to calculate retry-after
            oldest = r.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_ts = oldest[0][1]
                retry_after = int(WINDOW_SEC - (now - oldest_ts)) + 1
            else:
                retry_after = WINDOW_SEC
            return False, max(1, retry_after)

        return True, 0

    except redis.RedisError as e:
        # If Redis is down, allow the request (fail open)
        logger.warning(f"[RATE_LIMIT] Redis error, allowing request: {e}")
        return True, 0
