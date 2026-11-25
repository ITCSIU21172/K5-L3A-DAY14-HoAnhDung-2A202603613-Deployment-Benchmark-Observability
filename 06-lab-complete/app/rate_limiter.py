"""
Rate limiting (tiêu chí 7).
"""
import os
import time
import redis
from fastapi import HTTPException, status
from app.config import settings


def get_redis():
    url = os.getenv("REDIS_URL", settings.redis_url)
    return redis.from_url(url, decode_responses=True, socket_timeout=2.0)


def check_rate_limit(key: str) -> None:
    now = time.time()
    window_start = now - 60.0
    redis_key = f"rate_limit:{key}"
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", settings.rate_limit_per_minute))

    r = get_redis()
    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.zrange(redis_key, 0, 0, withscores=True)
        results = pipe.execute()

        current_count = results[1]
        oldest_entry = results[2]

        if current_count >= limit:
            retry_after = 60
            if oldest_entry:
                oldest_ts = oldest_entry[0][1]
                retry_after = max(1, int(oldest_ts + 60.0 - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {limit} requests per minute",
                headers={"Retry-After": str(retry_after)},
            )

        pipe2 = r.pipeline()
        pipe2.zadd(redis_key, {f"{now}": now})
        pipe2.expire(redis_key, 65)
        pipe2.execute()
    except HTTPException:
        raise
    except Exception as e:
        # Nếu Redis tạm thời lỗi thì không chặn request
        pass
