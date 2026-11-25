# ============================================================
# STAGE 1: Builder
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ============================================================
# STAGE 2: Runtime
# ============================================================
FROM python:3.11-slim AS runtime

# Tạo user non-root
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Copy python packages & binaries từ stage builder
COPY --from=builder /usr/local /usr/local

# Copy application source code
COPY . .

# Phân quyền cho appuser
RUN chown -R appuser:appuser /app

USER appuser

ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", 8000)}/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
