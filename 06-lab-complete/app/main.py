"""
Production AI Agent — Part 6 Final Project
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_cost
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ──────────────────────────────────────────────────────────
# Structured JSON Logging (Tiêu chí 10)
# ──────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "props") and isinstance(record.props, dict):
            data.update(record.props)
        return json.dumps(data)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.handlers = [handler]
logger.propagate = False


# ──────────────────────────────────────────────────────────
# Lifespan — Graceful Shutdown (Tiêu chí 11)
# ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...", extra={"props": {"event": "startup", "port": settings.port}})
    yield
    # Graceful Shutdown
    logger.info("Application shutting down gracefully...", extra={"props": {"event": "shutdown"}})


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


# ──────────────────────────────────────────────────────────
# Health check & Readiness endpoints (Tiêu chí 4 & 5)
# ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe: luôn trả 200 khi process đang chạy, kể cả khi Redis chưa sẵn sàng."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness probe: 200 khi Redis kết nối được, 503 khi Redis mất kết nối."""
    if not redis_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )
    return {"status": "ready"}


# ──────────────────────────────────────────────────────────
# Protected Ask Endpoint (Tiêu chí 6, 7, 8)
# ──────────────────────────────────────────────────────────
@app.post("/ask")
async def ask(
    request: Request,
    body: AskRequest | None = None,
    question: str | None = None,
    api_key: str = Depends(verify_api_key),
):
    start_ts = time.time()

    # Nhận question từ body JSON hoặc query param
    q = ""
    if body and body.question:
        q = body.question.strip()
    elif question:
        q = question.strip()
    else:
        try:
            raw = await request.json()
            q = (raw.get("question") or "").strip()
        except Exception:
            q = ""

    if not q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'question' is required",
        )

    # 1. Rate limiting (Tiêu chí 7) — 429 nếu vượt
    check_rate_limit(api_key)

    # 2. Cost guard (Tiêu chí 8) — 402 nếu hết ngân sách
    check_budget(api_key)

    # 3. Gọi LLM
    answer = llm_ask(q)

    # 4. Ghi nhận chi phí token vào Redis
    in_tokens = len(q.split()) * 2
    out_tokens = len(answer.split()) * 2
    cost = record_cost(in_tokens, out_tokens, api_key)

    elapsed_ms = round((time.time() - start_ts) * 1000, 2)
    logger.info(
        "Handled /ask request",
        extra={
            "props": {
                "event": "request_completed",
                "path": "/ask",
                "status": 200,
                "duration_ms": elapsed_ms,
                "cost_usd": cost,
            }
        },
    )

    return {"question": q, "answer": answer}
