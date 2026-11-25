"""
API Key authentication (tiêu chí 6).
"""
import os
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency cho FastAPI: đọc header X-API-Key và so sánh với AGENT_API_KEY."""
    expected_key = os.getenv("AGENT_API_KEY", settings.agent_api_key)
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Include header: X-API-Key: <your-key>",
        )
    return api_key
