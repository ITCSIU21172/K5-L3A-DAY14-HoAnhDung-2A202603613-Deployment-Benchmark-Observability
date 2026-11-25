"""
Cost guard (tiêu chí 8).
"""
import os
import logging
from datetime import datetime
import redis
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def get_redis():
    url = os.getenv("REDIS_URL", settings.redis_url)
    return redis.from_url(url, decode_responses=True, socket_timeout=2.0)


def _get_key(api_key: str | None = None) -> str:
    current_key = api_key or os.getenv("AGENT_API_KEY", settings.agent_api_key)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    return f"cost:{current_key}:{date_str}"


def check_budget(api_key: str | None = None) -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    daily_limit = float(os.getenv("DAILY_BUDGET_USD", settings.daily_budget_usd))
    monthly_limit = float(os.getenv("MONTHLY_BUDGET_USD", settings.monthly_budget_usd))
    budget_limit = min(daily_limit, monthly_limit)
    redis_key = _get_key(api_key)

    r = get_redis()
    try:
        spent = float(r.get(redis_key) or 0.0)
        if spent >= budget_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Budget exceeded: spent ${spent:.6f} / budget ${budget_limit:.6f}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking budget in Redis: {e}")


def record_cost(input_tokens: int, output_tokens: int, api_key: str | None = None) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    redis_key = _get_key(api_key)

    r = get_redis()
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(redis_key, cost)
        pipe.expire(redis_key, 86400 * 2)  # Lưu trong 2 ngày
        pipe.execute()
    except Exception as e:
        logger.warning(f"Error recording cost in Redis: {e}")
    return cost
