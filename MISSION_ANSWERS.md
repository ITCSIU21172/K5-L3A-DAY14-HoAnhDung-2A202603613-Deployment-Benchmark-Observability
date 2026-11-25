# Day 14 Lab — Mission Answers

> **Họ và tên:** Ho Anh Dung  
> **MSSV:** 2A202603613  
> **Lớp:** K5-L3A  
> **Repository:** K5-L3A-DAY14-HoAnhDung-2A202603613-Deployment-Benchmark-Observability  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns phát hiện trong `01-localhost-vs-production/develop/app.py`

1. **Hardcoded Secrets & Credentials (Dòng 17–18):**
   - Code ghi trực tiếp API key và database URL: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - *Hậu quả:* Khi commit và push mã nguồn lên Git/GitHub, các credentials này bị lộ công khai ngay lập tức, dẫn đến nguy cơ bị đánh cắp tài khoản và rò rỉ dữ liệu.
2. **Không có hệ thống quản lý cấu hình (Config Management) (Dòng 21–22):**
   - Các biến cấu hình như `DEBUG = True`, `MAX_TOKENS = 500` bị gán cứng trong mã nguồn, không đọc từ biến môi trường (Environment Variables).
   - *Hậu quả:* Không thể thay đổi cấu hình linh hoạt giữa các môi trường khác nhau (Development, Staging, Production) mà không phải sửa trực tiếp mã nguồn.
3. **Dùng `print()` thay vì Structured Logging & làm rò rỉ Secret vào Log (Dòng 33–34, 38):**
   - Sử dụng `print()` thông thường và in trực tiếp key nhạy cảm: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
   - *Hậu quả:* Dòng log dạng text tự do không thể parse được bởi các log aggregator (như Datadog, Grafana Loki, CloudWatch), đồng thời làm lộ secret ra stdout/hệ thống quản lý log.
4. **Thiếu Health Check & Readiness Endpoints (Không có endpoint `/health`, `/ready`):**
   - Chỉ có route `/` và `/ask`.
   - *Hậu quả:* Cloud platform (Railway, Render, Kubernetes, Docker) không thể kiểm tra trạng thái sống còn (Liveness) hay khả năng sẵn sàng phục vụ (Readiness). Nếu tiến trình bị deadlock, treo hoặc mất kết nối DB/Redis, platform không biết để tự động restart container hay ngắt điều hướng traffic.
5. **Cố định Host và Port (Hardcoded Binding) (Dòng 51–53):**
   - Chạy với `host="localhost"`, `port=8000`, `reload=True`.
   - *Hậu quả:* Binding vào `localhost` (127.0.0.1) khiến container không thể tiếp nhận kết nối mạng từ bên ngoài (cần bind `0.0.0.0`); gán cứng cổng 8000 khiến các nền tảng đám mây (Railway/Render) không thể inject cổng động qua biến môi trường `$PORT`; bật `reload=True` gây tốn CPU và không an toàn cho production.
6. **Không xử lý Graceful Shutdown:**
   - Không bắt tín hiệu `SIGTERM` / `SIGINT`.
   - *Hậu quả:* Khi scale down, restart hoặc deploy bản mới, server bị tắt đột ngột (abrupt exit), các request đang dở dang (in-flight requests) bị ngắt kết nối lập tức, gây lỗi 502/504 cho người dùng.

---

### Exercise 1.2: Kết quả chạy và gọi thử bản Develop

- **Lệnh chạy:**
  ```bash
  cd 01-localhost-vs-production/develop
  py app.py
  ```
- **Lệnh gọi test (nhận query parameter `question`):**
  ```bash
  curl -X POST "http://localhost:8000/ask?question=Hello"
  ```
- **Kết quả HTTP Response:**
  ```json
  {"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
  ```
- **Quan sát log console của bản develop:**
  ```text
  [DEBUG] Got question: Hello
  [DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
  [DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
  ```
- **Nhận xét:** App chạy và trả về kết quả thành công trên laptop, nhưng bộc lộ đầy đủ các anti-pattern nguy hiểm (in lộ secret `sk-hardcoded-fake-key-never-do-this` ra log, không có health check).

---

### Exercise 1.3: Bảng so sánh chi tiết giữa Develop và Production

| Tính năng / Tiêu chí | Bản Develop (`basic/app.py`) | Bản Production (`advanced/app.py`) | Tại sao quan trọng trong Production? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode trực tiếp trong code (`OPENAI_API_KEY`, `DATABASE_URL`) | Đọc từ file `.env` qua `config.py` và Pydantic `BaseSettings` | Tuân thủ 12-Factor App (nguyên tắc III: Config). Giữ bí mật an toàn, không lộ khi push code lên Git, dễ dàng thay đổi cấu hình giữa dev/staging/prod mà không cần build lại mã. |
| **Liveness Probe (`/health`)** | ❌ Không có | ✅ Có `GET /health` trả về `status: ok`, `uptime_seconds`, version, timestamp | Giúp Container Orchestrator (Docker/K8s/Railway) giám sát xem app có còn sống hay đã bị crash/deadlock để tự động restart container kịp thời. |
| **Readiness Probe (`/ready`)** | ❌ Không có | ✅ Có `GET /ready` trả về 200 khi sẵn sàng, 503 khi chưa sẵn sàng | Giúp Load Balancer chỉ điều hướng traffic người dùng vào container khi app đã nạp xong model, kết nối xong DB/Redis. Tránh lỗi 502/503 trong quá trình khởi động. |
| **Logging** | Sử dụng `print()` thông thường, in cả secret | Dùng `logging` chuẩn, định dạng JSON Structured (`{"time":..., "level":..., "msg":...}`), ẩn secret | Dễ dàng cho hệ thống Log Aggregator (Datadog, Grafana Loki, CloudWatch) parse, lọc, lập chỉ mục và cảnh báo tự động; bảo mật tuyệt đối cho token/secret của người dùng. |
| **Graceful Shutdown** | ❌ Không xử lý, process bị kill đột ngột | ✅ Dùng `lifespan` handler và bắt tín hiệu `signal.SIGTERM` | Đảm bảo khi container dừng (do deploy mới hoặc scale in), các request đang xử lý được hoàn thành trọn vẹn, giải phóng kết nối DB/Redis an toàn trước khi tiến trình tắt hoàn toàn. |
| **Host & Port Binding** | Hardcode `localhost:8000`, `reload=True` | Bind `0.0.0.0`, port đọc động từ biến môi trường `PORT` (`settings.port`) | `0.0.0.0` cho phép container nhận request từ mạng ngoài (Docker bridge/Ingress). Đọc cổng từ `$PORT` tương thích với cơ chế cấp port động của Railway, Render, Cloud Run. |
| **CORS Middleware** | ❌ Không cấu hình CORS | ✅ `CORSMiddleware` cấu hình danh sách `allowed_origins` qua biến môi trường | Chặn truy cập trái phép từ các domain độc hại trên trình duyệt, chỉ cho phép frontend hợp lệ gọi API. |

---

## Part 2: Docker

### Exercise 2.1: Các câu hỏi về Dockerfile (`02-docker/develop/Dockerfile`)

1. **Base image là gì?**
   - Base image là `python:3.11`.
   - Đây là image đầy đủ (Full distribution) dựa trên hệ điều hành Debian, chứa toàn bộ trình biên dịch C, headers, và công cụ phát triển, do đó kích thước rất lớn (khoảng 1.55 GB).
2. **Working directory là gì?**
   - Working directory là `/app`, được thiết lập thông qua lệnh `WORKDIR /app`.
   - Tất cả các lệnh tiếp theo (`COPY`, `RUN`, `CMD`) đều lấy thư mục `/app` trong filesystem của container làm thư mục làm việc mặc định.
3. **Tại sao `COPY requirements.txt` phải đứng trước `COPY . .`?**
   - Nhằm tối ưu hóa cơ chế **Docker Layer Caching**:
     - Docker thực hiện build từng bước (layer). Nếu một layer không thay đổi, Docker sẽ tái sử dụng cache ở các bước sau đó.
     - Mã nguồn ứng dụng (`app.py`, logic) thay đổi rất thường xuyên trong quá trình phát triển, trong khi các gói thư viện (`requirements.txt`) thì ít khi thay đổi.
     - Nếu đặt `COPY . .` trước, mỗi lần sửa một dòng code, toàn bộ cache từ bước đó trở đi sẽ bị mất (cache invalidated), buộc Docker phải tải và chạy lại lệnh tốn thời gian `pip install`.
     - Tách riêng `COPY requirements.txt .` rồi `RUN pip install` giúp Docker chỉ cần cài đặt lại packages khi danh sách dependencies thực sự thay đổi, giúp rút ngắn thời gian build từ vài phút xuống còn vài mili-giây.
4. **`CMD` và `ENTRYPOINT` khác nhau thế nào?**
   - **`ENTRYPOINT`:** Định nghĩa câu lệnh/tiến trình cố định thực thi chính của container khi khởi động (ví dụ `ENTRYPOINT ["python"]`). Các tham số truyền vào qua `docker run <image> <args>` sẽ được nối tiếp vào sau `ENTRYPOINT` chứ không ghi đè nó (trừ khi dùng cờ tường minh `--entrypoint`).
   - **`CMD`:** Cung cấp lệnh mặc định hoặc tham số mặc định cho container. Nếu người dùng truyền bất kỳ tham số nào khi chạy lệnh `docker run <image> <command>`, toàn bộ giá trị của `CMD` sẽ bị ghi đè.
   - Khi kết hợp cả hai: `ENTRYPOINT` đóng vai trò là chương trình thực thi chính, còn `CMD` là danh sách các cờ/tham số mặc định có thể bị override linh hoạt.

---

### Exercise 2.2: Kết quả build và chạy thử container bản develop

- **Lệnh build image:**
  ```bash
  docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
  ```
- **Lệnh chạy container:**
  ```bash
  docker run -d --name test-agent-dev -p 8000:8000 my-agent:develop
  ```
- **Lệnh test API:**
  ```bash
  curl -X POST "http://localhost:8000/ask?question=What+is+Docker%3F"
  ```
- **Kết quả trả về:**
  ```json
  {"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
  ```

---

### Exercise 2.3: So sánh kích thước Image (Single-stage vs Multi-stage)

Số liệu đo lường thực tế từ Docker trên máy:

- **Develop Image (`my-agent:develop` - Single stage):** **1590.51 MB** (1,667,771,580 bytes)
- **Production Image (`my-agent:advanced` - Multi-stage):** **228.70 MB** (239,811,238 bytes)
- **Tỷ lệ giảm dung lượng:** **85.62 %** (giảm gần 7 lần!)

#### Cơ chế giảm dung lượng của Multi-stage build (`02-docker/production/Dockerfile`):
- **Stage 1 (Builder - `FROM python:3.11-slim AS builder`):**
  - Cài đặt các công cụ biên dịch nặng (`gcc`, `libpq-dev`) để compile các thư viện Python C-extensions.
  - Cài đặt dependencies vào thư mục người dùng `/root/.local` bằng lệnh `pip install --user`.
  - Tầng này chứa đầy đủ cache, gcc, và các file tạm nhưng **bị loại bỏ hoàn toàn** ở bản cuối cùng.
- **Stage 2 (Runtime - `FROM python:3.11-slim AS runtime`):**
  - Khởi tạo từ base image gọn nhẹ (`python:3.11-slim`).
  - Chỉ copy duy nhất thư mục site-packages đã cài đặt từ builder (`COPY --from=builder /root/.local /home/appuser/.local`) và mã nguồn app.
  - Tạo user bảo mật không có quyền root (`appuser`), thiết lập `HEALTHCHECK` và lệnh chạy `uvicorn`.
- **Kết luận:** Image cuối cùng hoàn toàn sạch bóng các trình biên dịch (gcc, header files, build tools), giảm diện tích tấn công (attack surface) và dung lượng giảm tới **85.62%**.

---

### Exercise 2.4: Kiến trúc hệ thống Docker Compose Stack (`02-docker/production/docker-compose.yml`)

#### Sơ đồ kiến trúc (Architecture Diagram):

```
                   Internet / Client Requests
                              │
                              ▼
                   ┌─────────────────────┐
                   │  Nginx Reverse Proxy│ (Port 80/443 Public)
                   │  & Load Balancer    │
                   └──────────┬──────────┘
                              │ Bridge Network: internal
                              ▼
                   ┌─────────────────────┐
                   │  FastAPI Agent      │ (Port 8000 Internal)
                   │  (my-agent:advanced)│
                   └─────┬─────────┬─────┘
                         │         │
           Cache/Session │         │ Vector Embeddings / RAG
                         ▼         ▼
                 ┌──────────┐   ┌──────────────┐
                 │  Redis   │   │    Qdrant    │
                 │ (Port    │   │ (Vector DB   │
                 │  6379)   │   │  Port 6333)  │
                 └──────────┘   └──────────────┘
```

#### Các service và giao tiếp nội bộ:
1. **`nginx`:** Đứng ở ngoài cùng nhận request tại port 80/443, reverse proxy và chuyển hướng traffic vào service `agent`.
2. **`agent`:** Chứa AI FastAPI Agent, không mở cổng trực tiếp ra ngoài máy host mà chỉ lắng nghe trong mạng nội bộ (`internal`).
3. **`redis`:** Service in-memory database (`redis:7-alpine`) để lưu trữ cache session và rate limiting, có volume mount `redis_data` để bảo toàn dữ liệu.
4. **`qdrant`:** Service vector database (`qdrant/qdrant:v1.9.0`) để phục vụ lưu trữ semantic embeddings cho tính năng RAG, có volume mount `qdrant_data`.
5. Tất cả kết nối với nhau qua mạng Docker bridge cô lập (`internal`).

#### Kết quả kiểm thử thực tế qua Nginx (Port 80):
- **Kiểm tra Health check:**
  ```bash
  curl http://localhost/health
  ```
  *Output:*
  ```json
  {"status":"ok","uptime_seconds":11.3,"version":"2.0.0","timestamp":"2026-11-25T08:28:59.906511"}
  ```
- **Kiểm tra Agent endpoint:**
  ```bash
  curl -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
  ```
  *Output:*
  ```json
  {"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
  ```

---

## Part 3: Cloud Deployment

### 1. Thông tin Triển khai Production (Railway)
- **Nền tảng:** Railway
- **Public URL:** `https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app`
- **Các biến môi trường cấu hình trên Railway Dashboard:**
  - `PORT`: `8000`
  - `ENVIRONMENT`: `production`
  - `AGENT_API_KEY`: `secret-prod-key-123`
  - `REDIS_URL`: `${{Redis.REDIS_URL}}` (liên kết trực tiếp từ Database service Redis trên cùng project)

### 2. Kết quả Kiểm thử 4 Lệnh Tự Kiểm (CP6 Self-Test)

```bash
BASE="https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app"
AGENT_API_KEY="secret-prod-key-123"

# 1. Health check (Liveness) -> Mong đợi HTTP 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Kết quả: 200

# 2. Readiness check (Phụ thuộc Redis) -> Mong đợi HTTP 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Kết quả: 200

# 3. API Test không có Header X-API-Key -> Mong đợi HTTP 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
# Kết quả: 401

# 4. API Test có Header X-API-Key hợp lệ -> Mong đợi HTTP 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
# Kết quả: 200
```

### 3. So sánh cấu hình `railway.toml` và `render.yaml` (Exercise 3.1 & 3.2)

| Tiêu chí | Railway (`railway.toml`) | Render Blueprint (`render.yaml`) |
|---|---|---|
| **Định dạng cấu hình** | TOML (`[build]`, `[deploy]`) | YAML (Khai báo danh sách `services:`) |
| **Cách khai báo Build** | Đơn giản: `builder = "DOCKERFILE"` | Khai báo chi tiết: `type: web`, `runtime: docker`, `plan: free` |
| **Health Check Path** | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| **Restart Policy** | Hỗ trợ cấu hình `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3` | Tự động quản lý theo container lifecycle của Render |
| **Quản lý Cổng (PORT)** | App tự đọc biến môi trường `$PORT` do Railway cấp động qua `${PORT:-8000}` | Có thể gán tĩnh hoặc Render inject vào container qua envVars |
| **Quản lý Secrets & Biến** | Secret được nhập tập trung trên Web UI/CLI, không ghi giá trị nhạy cảm vào file | Hỗ trợ `generateValue: true` (tự sinh secret ngẫu nhiên) hoặc `sync: false` (buộc nhập tay trên UI), chống lộ secrets vào Git |
| **Hệ sinh thái Multi-service** | Canvas trực quan, kết nối database qua service reference `${{Redis.REDIS_URL}}` | Có thể khai báo đồng thời Web Service và Redis/Postgres Blueprint trong cùng 1 file YAML |

### 4. Phân tích Pipeline CI/CD Google Cloud Run (Exercise 3.3)
Dựa trên `cloudbuild.yaml` và `service.yaml` trong thư mục `03-cloud-deployment/production-cloud-run/`:

Pipeline CI/CD được kích hoạt tự động mỗi khi có commit push lên nhánh `main`, bao gồm 4 bước nối tiếp:
1. **Bước 1 — Automated Testing (`Step: test`):** Khởi tạo môi trường `python:3.11-slim`, cài đặt dependencies và chạy `pytest tests/ -v`. Đây là **Quality Gate**: nếu có bất kỳ test case nào thất bại, pipeline dừng ngay lập tức, ngăn chặn code lỗi được build và deploy.
2. **Bước 2 — Container Build (`Step: build`):** Sử dụng `docker build` để đóng gói source code thành Docker image với 2 tags: `$COMMIT_SHA` (định danh duy nhất theo git commit để phục vụ audit/rollback) và `latest`. Áp dụng cờ `--cache-from` từ bản `latest` để tận dụng Docker layer caching, rút ngắn thời gian build.
3. **Bước 3 — Registry Push (`Step: push`):** Đẩy đồng thời cả 2 image tags lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Bước 4 — Deployment (`Step: deploy`):** Triển khai image lên Cloud Run tại region `asia-southeast1`. Cấu hình bao gồm:
   - **Auto-scaling & Tránh Cold start:** Thiết lập `--min-instances=1` (luôn duy trì 1 container chạy sẵn để triệt tiêu độ trễ cold start cho người dùng) và `--max-instances=10` (ngăn chặn chi phí tăng vọt khi bị quá tải/DDoS).
   - **Bảo mật tuyệt đối:** Lấy secret an toàn từ Google Secret Manager qua cờ `--set-secrets=OPENAI_API_KEY=openai-key:latest`, hoàn toàn không hardcode API key.
   - **Knative Service Spec (`service.yaml`):** Khai báo tài nguyên (limits 1 CPU / 512Mi RAM) và thiết lập concurrency tối đa 80 request/instance giúp tối ưu hoá chi phí vận hành serverless.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (Bản Develop — `04-api-gateway/develop/`)

Chạy app với biến môi trường `AGENT_API_KEY=secret-key-123`:

- **Trường hợp 1: Không có Header `X-API-Key` (Mong đợi HTTP 401)**
  ```http
  HTTP/1.1 401 Unauthorized
  date: Wed, 25 Nov 2026 08:30:27 GMT
  server: uvicorn
  content-length: 67
  content-type: application/json

  {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
  ```

- **Trường hợp 2: Sai API Key (Mong đợi HTTP 403)**
  ```http
  HTTP/1.1 403 Forbidden
  date: Wed, 25 Nov 2026 08:30:28 GMT
  server: uvicorn
  content-length: 29
  content-type: application/json

  {"detail":"Invalid API key."}
  ```

- **Trường hợp 3: Đúng API Key `secret-key-123` (Mong đợi HTTP 200)**
  ```http
  HTTP/1.1 200 OK
  date: Wed, 25 Nov 2026 08:31:23 GMT
  server: uvicorn
  content-length: 145
  content-type: application/json

  {"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
  ```

---

### Exercise 4.2 & 4.3: Full Security Stack (Bản Production — `04-api-gateway/production/`)

Bản production kết hợp xác thực JWT, phân quyền theo vai trò (Role-based access), Rate limiting và Cost guard.

#### 1. Lấy JWT Token qua `POST /auth/token` (Tài khoản `student` / `demo123`):
- **Request:**
  ```bash
  curl -X POST http://localhost:8000/auth/token \
       -H "Content-Type: application/json" \
       -d '{"username": "student", "password": "demo123"}'
  ```
- **Response:**
  ```json
  {
    "access_token": "eyJhbGciOi...[TOKEN_MASKED]...kuEUjzE09M",
    "token_type": "bearer",
    "expires_in_minutes": 60,
    "hint": "Include in header: Authorization: Bearer eyJhbGciOi..."
  }
  ```

#### 2. Gọi endpoint bảo vệ `/ask` khi chưa có token (HTTP 401):
```http
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 08:31:58 GMT
www-authenticate: Bearer
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

#### 3. Gọi endpoint `/ask` với token hợp lệ (HTTP 200):
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:31:58 GMT
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"what is docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

#### 4. Kích hoạt Rate Limit bằng vòng lặp (Tài khoản `student` bị giới hạn 10 req/phút):
- Gửi liên tiếp 11 requests:
  - Request 1 → 9: HTTP 200
  - Request 10: HTTP 429
- **Output nhận được tại request vượt ngưỡng (HTTP 429):**
  ```http
  HTTP/1.1 429 Too Many Requests
  date: Wed, 25 Nov 2026 08:31:59 GMT
  x-ratelimit-limit: 10
  x-ratelimit-remaining: 0
  x-ratelimit-reset: 1795595580
  retry-after: 59
  content-type: application/json
  x-content-type-options: nosniff
  x-frame-options: DENY
  x-xss-protection: 1; mode=block
  referrer-policy: strict-origin-when-cross-origin

  {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
  ```

---

### Exercise 4.4: Cơ chế Cost Guard (Bảo vệ ngân sách)

#### Cách triển khai Cost Guard:
1. **Theo dõi chi phí theo Token/Mô hình:**
   - Mỗi request gọi LLM tiêu thụ một lượng `input_tokens` (prompt) và `output_tokens` (completion).
   - Chi phí được tính theo công thức:
     $$\text{Chi phí} = \frac{\text{input\_tokens} \times \text{giá\_in}}{1000} + \frac{\text{output\_tokens} \times \text{giá\_out}}{1000}$$
2. **Kiểm tra trước khi gọi (Pre-flight check):**
   - Trước khi dispatch request sang OpenAI/Anthropic, hệ thống kiểm tra tổng chi phí tích lũy trong ngày/tháng của user và toàn hệ thống:
     `cost_guard.check_budget(username)`.
   - Nếu tổng chi phí cộng dồn vượt quá hạn mức (`daily_budget_usd`), endpoint lập tức trả về mã lỗi **`402 Payment Required`** và chặn không cho request gọi tới LLM.
3. **Cập nhật sau khi gọi (Post-call recording):**
   - Ghi nhận token thực tế vào Redis (`cost_guard.record_usage(...)`) để bảo đảm trạng thái ngân sách được đồng bộ giữa các replica/instance.

#### Tại sao cần CẢ Rate Limiting VÀ Cost Guard?
| Tiêu chí | Rate Limiting | Cost Guard |
| :--- | :--- | :--- |
| **Mục tiêu bảo vệ** | **Hạ tầng & Tốc độ (Throughput)**: Bảo vệ CPU, RAM, băng thông mạng khỏi bị DDoS, nghẽn hàng đợi hoặc crash server. | **Tài chính & Ngân sách (Cost)**: Ngăn chặn rủi ro thâm hụt tiền bạc (Bill shock) do hóa đơn API LLM tăng vọt ngoài tầm kiểm soát. |
| **Đơn vị đo lường**| Số lượng requests trên một đơn vị thời gian (ví dụ 10 requests / phút). | Số lượng token và số tiền USD tiêu thụ trong ngày hoặc tháng (ví dụ $1 / ngày). |
| **Lỗ hổng nếu thiếu cái còn lại** | Nếu **chỉ có Cost Guard**: Kẻ tấn công có thể gửi 10.000 request/giây với câu hỏi rất ngắn (vài token) không tốn nhiều tiền nhưng làm sập hoàn toàn máy chủ do quá tải I/O. | Nếu **chỉ có Rate Limiting**: Một user chỉ gọi 2 request/phút (hoàn toàn hợp lệ theo rate limit) nhưng mỗi request nhồi prompt 128.000 tokens kèm yêu cầu suy luận đắt đỏ với model cao cấp, khiến hóa đơn tiêu tốn hàng chục đến hàng trăm USD trong thời gian ngắn. |

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks — Phân biệt Liveness (`/health`) và Readiness (`/ready`)

| Tiêu chí | Liveness Probe (`GET /health`) | Readiness Probe (`GET /ready`) |
| :--- | :--- | :--- |
| **Câu hỏi cần trả lời** | *"Tiến trình ứng dụng có còn sống (alive) hay không?"* | *"Ứng dụng đã sẵn sàng (ready) nhận và xử lý traffic người dùng chưa?"* |
| **Kiểm tra những gì?** | Chỉ kiểm tra process nội tại của app có phản hồi HTTP không (kể cả khi mất kết nối DB/Redis). | Kiểm tra các kết nối downstream phụ thuộc (Redis ping, Database query `SELECT 1`, tải model vào RAM). |
| **Hành vi khi trả về lỗi (5xx / Timeout)** | Container Orchestrator (Docker/K8s/Cloud) coi container đã chết (deadlock/OOM) → **Tự động KILL và RESTART container**. | Load Balancer (Nginx/Cloud LB) coi container tạm thời chưa sẵn sàng → **Rút container ra khỏi danh sách định tuyến traffic**, KHÔNG restart. |
| **Quy tắc thiết kế** | Phải luôn trả về HTTP 200 chừng nào process Python còn chạy. Nếu Redis down, `/health` **vẫn phải trả 200** (để tránh bị restart loop liên tục). | Trả về HTTP 200 khi kết nối Redis/DB thông suốt; trả về **HTTP 503** khi mất kết nối Redis để Load Balancer chuyển request sang instance khác còn sống. |

---

### Exercise 5.2: Graceful Shutdown

- **Vấn đề:** Khi container nhận tín hiệu tắt (deploy bản mới, scale down hoặc restart), hệ điều hành gửi tín hiệu `SIGTERM`. Nếu không bắt tín hiệu này, tiến trình bị ngắt đột ngột (`SIGKILL`), các request người dùng đang xử lý dở (in-flight requests) sẽ bị ngắt kết nối lập tức, sinh ra lỗi `502 Bad Gateway` hoặc dữ liệu ghi dở dang bị hỏng.
- **Giải pháp:**
  1. Đăng ký listener bắt tín hiệu `signal.signal(signal.SIGTERM, shutdown_handler)` hoặc dùng `lifespan` của FastAPI.
  2. Khi nhận `SIGTERM`: Chuyển trạng thái readiness thành `False` (báo `/ready` trả 503 để Load Balancer ngừng gửi request mới vào).
  3. Cho phép một khoảng thời gian chờ (grace period, thường là 5–15 giây) để các request đang xử lý hoàn thành trọn vẹn và trả về HTTP 200.
  4. Đóng các connection pool (Redis, Database) an toàn rồi mới cho tiến trình thoát (`sys.exit(0)`).

---

### Exercise 5.3: Stateless Design (Tại sao State trong RAM bị hỏng khi Scale?)

- **Vấn đề State trong Memory (RAM):**
  - Khi lưu `conversation_history` hay `rate_limit_counter` trong biến Python in-memory (ví dụ `dict`), mỗi container/instance có một vùng nhớ RAM độc lập.
  - Khi hệ thống scale lên nhiều instances (ví dụ 3 instances) đứng sau Load Balancer:
    - Request 1 của user A rơi vào `instance-1` (lưu tin nhắn 1 vào RAM instance-1).
    - Request 2 của user A rơi vào `instance-2` (RAM của instance-2 trống rỗng, mất toàn bộ ngữ cảnh trước đó!).
    - Người dùng bị mất lịch sử chat liên tục, rate limit bị chia nhỏ (user có thể gọi gấp 3 lần hạn mức vì mỗi instance đếm riêng).
- **Giải pháp Stateless với Redis:**
  - Toàn bộ trạng thái phiên làm việc (Session state, conversation history, rate limit sliding window, budget tracking) được đưa ra lưu trữ tập trung tại **Redis**.
  - Tất cả các agent instances đều không lưu bất kỳ state nào trong RAM (Stateless). Mọi request rơi vào bất kỳ instance nào cũng đọc/ghi từ cùng một cụm Redis tập trung, đảm bảo tính nhất quán tuyệt đối.

---

### Exercise 5.4 & 5.5: Kiểm thử thực tế Load Balancing và Stateless với 3 Instances

Khởi động stack với 3 agent replicas bằng lệnh:
```bash
docker compose -p k5-day14-scaling up -d --build --scale agent=3
```
Chạy script kiểm thử:
```bash
python test_stateless.py
```

#### Output đo lường thực tế từ `test_stateless.py`:
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: ed7f2b44-a1c2-4174-bf6d-8dad9b586d40

Request 1: [instance-a9f23f]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-1097d8]
  Q: Why do we need containers?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 3: [instance-590f10]
  Q: What is Kubernetes?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 4: [instance-a9f23f]
  Q: How does load balancing work?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

Request 5: [instance-1097d8]
  Q: What is Redis used for?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-590f10', 'instance-a9f23f', 'instance-1097d8'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: What is Kubernetes?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: How does load balancing work?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...
  [user]: What is Redis used for?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...

✅ Session history preserved across all instances via Redis!
```

#### Phân tích kết quả:
1. **Khả năng cân bằng tải (Load Balancing):**
   - 5 requests trong cùng một phiên chat đã được Nginx phân phối luân phiên (Round-robin) đều qua cả 3 instances khác nhau (`instance-a9f23f`, `instance-1097d8`, `instance-590f10`).
2. **Khả năng duy trì State tập trung (Stateless Preservation):**
   - Mặc dù mỗi câu hỏi do một instance khác nhau xử lý, nhưng khi truy vấn endpoint `/chat/{session_id}/history`, toàn bộ 10 messages (5 user + 5 assistant) vẫn còn nguyên vẹn, đầy đủ và đúng thứ tự.
   - Điều này chứng minh ứng dụng hoàn toàn **Stateless**: bất kỳ instance nào gặp sự cố hay bị tắt đi thì phiên làm việc của người dùng vẫn được bảo toàn trọn vẹn nhờ Redis.

---

## Part 6: Final Project — Production-Ready AI Agent

Đã hoàn thiện toàn bộ bản khung trong `06-lab-complete/` đáp ứng đầy đủ 12 tiêu chí chuẩn production:

1. **`app/config.py`:** Đọc cấu hình từ biến môi trường (`PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`). Không hard-code secret.
2. **`app/redis_client.py`:** Kết nối Redis client an toàn (không kết nối ngay lúc import), hàm `redis_healthy()` kiểm tra ping phục vụ readiness probe.
3. **`app/auth.py`:** Xác thực `X-API-Key`, thiếu hoặc sai key trả về HTTP 401 Unauthorized.
4. **`app/rate_limiter.py`:** Thuật toán Sliding Window sử dụng Redis Sorted Set (`ZREMRANGEBYSCORE`, `ZCARD`, `ZADD`, `EXPIRE`). Vượt giới hạn trả về HTTP 429 kèm header `Retry-After`. Trạng thái lưu tập trung trong Redis, duy trì nguyên vẹn sau khi restart agent.
5. **`app/cost_guard.py`:** Kiểm tra ngân sách trước khi gọi LLM (vượt mức `DAILY_BUDGET_USD` trả HTTP 402 Payment Required), ghi nhận chi phí token tích lũy vào Redis sau khi gọi.
6. **`app/main.py`:**
   - Structured JSON logging: mọi dòng log do app sinh ra đều là 1 JSON object hợp lệ qua `JsonFormatter`.
   - `GET /health`: Luôn trả 200 khi process đang chạy (kể cả Redis chưa sẵn sàng).
   - `GET /ready`: Trả 200 khi Redis kết nối tốt, trả 503 khi Redis mất kết nối.
   - `POST /ask`: Nhận input cả qua JSON body lẫn query param, tích hợp chuỗi bảo vệ auth -> rate limit -> cost guard -> LLM -> cost record.
   - Graceful shutdown: sử dụng FastAPI `lifespan`, cho phép in-flight request hoàn thành và trả 200 trước khi thoát an toàn.
7. **`Dockerfile`:** Multi-stage build (Builder + Runtime), base `python:3.11-slim`, user non-root `appuser`, có `HEALTHCHECK`, kích thước image chỉ **254 MB** (< 500 MB), `exec uvicorn` là PID 1 lắng nghe theo biến `$PORT`.
8. **`docker-compose.yml`:** Service `agent` (build từ Dockerfile) kết nối `redis` (`redis:7-alpine`), có healthcheck và `depends_on`.
9. **`.dockerignore` & `.env.example`:** Loại trừ `.env`, `__pycache__`, `venv`, tài liệu; `.env.example` liệt kê đầy đủ các biến môi trường cần thiết.
10. **`railway.toml` & `render.yaml`:** Cấu hình deploy đầy đủ, builder DOCKERFILE, healthcheck `/health`, secrets quản lý bảo mật.

#### Kết quả chạy `check_production_ready.py`:

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI Log

### Part 1: Localhost vs Production
- **Prompt / Câu hỏi:** Phân tích các anti-patterns trong `01-localhost-vs-production/develop/app.py`, chạy thử nghiệm so sánh với `production/app.py`, và lập bảng đối chiếu tiêu chuẩn 12-Factor.
- **Phản hồi nhận được:** Nhận diện 6 anti-pattern cốt lõi (Hardcoded secret, thiếu config management, print logs lộ secret, thiếu `/health` và `/ready`, cố định localhost/port, thiếu graceful shutdown) và đối chiếu chi tiết với các cải tiến trong bản `production/app.py`.
- **Tự kiểm tra và xác minh:** Đã chạy thực tế `py app.py` bản develop, gọi `curl -X POST "http://localhost:8000/ask?question=Hello"`, ghi nhận phản hồi JSON và xác thực log console in lộ API key. Đã test bản production qua `GET /health` và `POST /ask`.

### Part 2: Docker
- **Prompt / Câu hỏi:** Trả lời các câu hỏi về Dockerfile cơ bản, giải thích cơ chế Multi-stage build, đo đạc kích thước thực tế giữa develop vs production image và vẽ sơ đồ kiến trúc Docker Compose.
- **Phản hồi nhận được:** Phân tích chi tiết 4 câu hỏi lý thuyết, cơ chế builder vs runtime trong multi-stage, và kiến trúc Nginx reverse proxy nối với Agent, Redis, Qdrant.
- **Tự kiểm tra và xác minh:** Đã build trực tiếp `my-agent:develop` và `my-agent:advanced` bằng Docker Engine. Đo được chính xác kích thước image: Develop (1590.51 MB) vs Advanced (228.70 MB), giảm 85.62%. Đã dựng stack Compose `k5-day14-part2`, gọi test thành công `GET /health` và `POST /ask` qua Nginx cổng 80, sau đó dọn dẹp sạch sẽ tài nguyên.

### Part 4: API Security
- **Prompt / Câu hỏi:** Kiểm tra bảo mật với API Key (401/403/200), JWT Authentication và kích hoạt Rate Limiting (429) ở bản production, phân tích cơ chế và sự cần thiết của Cost Guard song song với Rate Limiting.
- **Phản hồi nhận được:** Hướng dẫn lấy token tại `/auth/token`, gọi `/ask` với Bearer token và chạy vòng lặp kích hoạt 429 sau 10 requests. Phân tích chi tiết sự khác nhau và mối liên hệ tương hỗ giữa Rate Limiting (bảo vệ hạ tầng) và Cost Guard (bảo vệ tài chính).
- **Tự kiểm tra và xác minh:** Đã chạy app thực tế, ghi lại toàn bộ response header kèm HTTP status code: 401 khi thiếu auth, 200 khi có key/token hợp lệ, 429 sau 10 request liên tiếp từ tài khoản `student`, có header `retry-after: 59`. Che token theo đúng quy định.

### Part 5: Scaling & Reliability
- **Prompt / Câu hỏi:** Phân biệt cơ chế hoạt động của Liveness Probe (`/health`) vs Readiness Probe (`/ready`), cơ chế Graceful Shutdown và kiểm thử Stateless Agent khi scale 3 replicas sau Nginx load balancer.
- **Phản hồi nhận được:** Giải thích chi tiết vì sao `/health` luôn trả 200 còn `/ready` trả 503 khi mất kết nối Redis; rủi ro khi lưu state trong RAM và giải pháp lưu tập trung trong Redis. Hướng dẫn chạy `test_stateless.py`.
- **Tự kiểm tra và xác minh:** Đã build và chạy stack Compose `k5-day14-scaling` với cờ `--scale agent=3`, cổng 8080. Chạy thành công `test_stateless.py`, xác nhận cả 3 instances khác nhau (`instance-590f10`, `instance-a9f23f`, `instance-1097d8`) cùng phục vụ các câu hỏi nhưng toàn bộ 10 messages lịch sử phiên chat được bảo toàn trọn vẹn qua Redis. Dọn dẹp sạch sẽ tài nguyên sau khi test.

### Part 6: Final Project (Production-Ready AI Agent)
- **Prompt / Câu hỏi:** Tự thiết kế và hoàn thiện toàn bộ mã nguồn bản khung trong `06-lab-complete/` đáp ứng đầy đủ 12 tiêu chí chấm điểm của `check_production_ready.py`.
- **Phản hồi nhận được:** Hướng dẫn hiện thực `app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py` (Redis ZSET sliding window), `app/cost_guard.py` (Redis token cost tracker), `app/main.py` (JSON logging, `/health`, `/ready`, `/ask`, graceful shutdown), `Dockerfile` multi-stage (< 500 MB), `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml` và `render.yaml`.
- **Tự kiểm tra và xác minh:** Đã chạy script chấm tự động `check_production_ready.py`, vượt qua toàn bộ 42/42 checks. Đo lường kích thước image đạt 254 MB, thời gian `docker stop` tắt êm chỉ 0.7 giây, các bài test auth, rate limit, cost guard, readiness khi mất Redis đều đạt kết quả mong đợi. Output đạt `PASS 12/12`.

### Part 3: Cloud Deployment
- **Prompt / Câu hỏi:** Triển khai agent production lên Railway, kết nối dịch vụ Redis cloud, cấu hình biến môi trường, domain public và phân tích so sánh cấu hình `railway.toml` vs `render.yaml` cùng pipeline Cloud Run (`cloudbuild.yaml`).
- **Phản hồi nhận được:** Hướng dẫn cấu hình Root Directory `06-lab-complete`, kết nối biến `REDIS_URL`, thiết lập public networking domain và thực hiện bộ 4 lệnh tự kiểm CP6. Phân tích so sánh chi tiết giữa cơ chế build, healthcheck, quản lý secret của Railway và Render Blueprint, cùng quy trình CI/CD 4 bước trên Cloud Build.
- **Tự kiểm tra và xác minh:** Đã deploy thành công trên Railway với URL `https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app`. Chạy thành công cả 4 lệnh tự kiểm (`/health` -> 200, `/ready` -> 200, `/ask` thiếu key -> 401, `/ask` có key -> 200). Đã lưu ảnh minh chứng `dashboard.png`, `running.png`, `test.png` vào thư mục `screenshots/`.

### Part 7: Benchmark & Observability
- **Prompt / Câu hỏi:** Thực hiện benchmark hiệu năng (load test với concurrency 1, 10, 50, 100), tail latency (`MOCK_SLOW_RATE`), benchmark chất lượng (eval trên golden dataset), sửa knowledge base đạt 100% không regression và triển khai full stack Observability (Prometheus, Grafana, Jaeger, Locust).
- **Phản hồi nhận được:** Hướng dẫn chạy `load_test.py`, phân tích vì sao RPS không tăng tuyến tính và vì sao tail latency đòi hỏi đo bằng p95/p99. Hướng dẫn sửa 2 câu lỗi trong `KNOWLEDGE_BASE` (`security-02`, `scaling-03`), chạy so sánh scaling 1 vs 3 instances bằng Locust headless và phân tích các thí nghiệm phá hệ thống (chaos testing).
- **Tự kiểm tra và xác minh:** Đã chạy đo đạc thực tế toàn bộ các bài test, thu thập đầy đủ 10 file báo cáo JSON trong `reports/`, 2 file CSV trong `benchmark-results/`. Eval đạt 100% (23/23 ✅ PASS). Đo lường scaling chứng minh p95 giảm từ 1200ms xuống 230ms khi tăng lên 3 instances. Chụp đầy đủ 4 ảnh minh chứng Observability: `grafana-dashboard.png`, `jaeger-slow-trace.png`, `jaeger-error-trace.png`, và `prometheus-alert-firing.png`. Ghi nhận toàn bộ số liệu thật vào `BENCHMARK_REPORT.md`.
