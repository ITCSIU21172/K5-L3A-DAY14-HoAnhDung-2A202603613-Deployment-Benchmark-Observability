"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import os
import logging
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Kết nối Redis client nhưng KHÔNG ping/kết nối ngay lúc import
r = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2.0)


def redis_healthy() -> bool:
    """Kiểm tra Redis sẵn sàng cho GET /ready."""
    try:
        current_url = os.getenv("REDIS_URL", settings.redis_url)
        client = redis.from_url(current_url, decode_responses=True, socket_timeout=1.5)
        return bool(client.ping())
    except Exception as e:
        logger.warning(f"Redis healthcheck failed: {e}")
        return False
