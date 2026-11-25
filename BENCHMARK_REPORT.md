# Benchmark & Observability Report — Day 14

**Họ tên:** Hồ Anh Dũng  
**MSSV:** 2A202603613  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows 11, Intel Core i5/i7 ThinkPad, Docker Desktop, Python 3.12.7  

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Người dùng tương tác trực tiếp (chat/voice) mong đợi phản hồi dưới 0.5s để cảm thấy mượt mà và không bị ngắt quãng dòng suy nghĩ. |
| Error rate `/ask` | < 2.0 % | Dự phòng lỗi mạng tạm thời hoặc upstream LLM provider trả 429/503 ngẫu nhiên (error budget 2%). |
| Accuracy trên golden dataset | ≥ 80 % | Đảm bảo tính chính xác về mặt chuyên môn của câu trả lời trước khi deploy bản mới ra production (chặn regression). |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.84 | 202.6 | 248.2 | 1697.0 | 0.67% | PASS |
| 10 | 32.83 | 197.9 | 458.8 | 1735.7 | 0.67% | PASS |
| 50 | 96.64 | 213.7 | 523.3 | 1726.0 | 2.00% | FAIL |
| 100 | 51.04 | 685.3 | 3780.0 | 4085.3 | 1.67% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- RPS **không** tăng tuyến tính theo concurrency:
  - Từ $c=1$ lên $c=10$, RPS tăng mạnh từ 3.84 lên 32.83 req/s (tăng ~8.5 lần, gần tuyến tính do CPU và event loop chưa bị nghẽn).
  - Từ $c=10$ lên $c=50$, RPS tiếp tục tăng đạt đỉnh tại 96.64 req/s, tuy nhiên latency p95 bắt đầu vượt ngưỡng 500ms (523.3ms) khiến SLO bị FAIL.
  - Từ $c=50$ lên $c=100$, RPS **sụt giảm nghiêm trọng** từ 96.64 xuống chỉ còn 51.04 req/s (giảm gần một nửa), trong khi latency p95 nhảy vọt lên tới 3780.0ms (~3.8s) và max latency lên tới 4.4s.
- **Nguyên nhân:** Đơn instance agent (chạy bằng Python/FastAPI/Uvicorn) có giới hạn về tài nguyên (CPU core, socket buffer, và asyncio event loop scheduling). Khi số lượng concurrent requests vượt quá điểm bão hoà (saturation point), các request bị dồn ứ trong hàng đợi (queuing delay), dẫn đến hiện tượng tranh chấp tài nguyên (resource contention) và suy giảm thông lượng (thrashing). Do đó, một instance đơn lẻ không thể mở rộng tuyến tính mãi; để xử lý mức concurrency cao hơn, bắt buộc phải scale ngang (horizontal scaling) nhiều replicas phía sau load balancer.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 209.2 | 248.1 | 481.2 |
| 0.03 (mặc định) | 252.4 | 486.4 | 1689.5 |
| 0.1 | 397.6 | 1693.9 | 1724.3 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- Chỉ số nhạy nhất với request chậm là **p95** và **p99**:
  - Khi tỉ lệ request chậm `MOCK_SLOW_RATE` tăng từ 0 lên 0.1 (10% số request bị chậm bất thường):
    - Latency trung bình (`avg`) chỉ tăng từ 209.2ms lên 397.6ms (tăng ~90%, vẫn nằm dưới ngưỡng 500ms, tạo cảm giác sai lệch rằng toàn bộ hệ thống vẫn chạy ổn).
    - Trong khi đó, `p95` nhảy vọt từ 248.1ms lên **1693.9ms** (tăng tới gần 7 lần, gấp hơn 3 lần ngưỡng SLO 500ms).
    - `p99` nhảy vọt từ 481.2ms lên **1724.3ms** ngay từ khi `MOCK_SLOW_RATE` chỉ mới ở mức 0.03.
- **Vì sao không nên đặt SLO theo average:**
  - Latency trung bình bị "làm phẳng" bởi số đông các request nhanh (90% request hoàn thành trong ~150-200ms kéo chỉ số trung bình xuống thấp), che lấp hoàn toàn sự cố của 5–10% người dùng thực tế đang phải chờ đợi gần 2 giây.
  - Nếu chỉ nhìn vào average, đội ngũ vận hành sẽ bỏ lỡ sự cố nghiêm trọng (silent degradation). Đo lường theo percentile (p95, p99) phản ánh chính xác trải nghiệm của nhóm người dùng gặp đuôi trễ (tail latency), giúp phát hiện tắc nghẽn upstream, lock database hay GC pauses kịp thời.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 56.6 | 108.8 | 112.2 |
| Tổng cost (USD) | $0.000397 | $0.000758 | $0.000778 |
| Cost / câu đúng (USD) | $0.00039735 | $0.00003607 | $0.00003381 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `["token", "hết hạn", "chữ ký"]` | Thêm entry kiến thức vào `KNOWLEDGE_BASE` trong `mock_llm.py` kích hoạt bởi `["jwt", "xác thực", "api key"]`, giải thích JWT là token có thời hạn và chữ ký số. |
| `scaling-03` | `["cpu", "memory", "custom metrics"]` | Thêm entry kiến thức vào `KNOWLEDGE_BASE` trong `mock_llm.py` kích hoạt bởi `["hpa", "kubernetes", "k8s"]`, giải thích HPA tự động scale dựa trên CPU, Memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **Về chất lượng (Accuracy):** Agent v2 áp dụng RAG (truy xuất tri thức từ knowledge base) tạo ra bước nhảy vọt từ 4.3% lên 91.3% và đạt tuyệt đối 100% sau khi bổ sung đủ dữ liệu tri thức. Agent v1 hoàn toàn không có retrieval nên chỉ trả về các câu trả lời chung chung mang tính placeholder.
- **Về chi phí (Cost):**
  - Chi phí mỗi request ở v2 cao hơn ~1.9 lần so với v1 (avg tokens tăng từ 56.6 lên 112.2 do phải kèm thêm ngữ cảnh retrieved context vào prompt gửi cho LLM).
  - **Tuy nhiên, chi phí trên mỗi câu trả lời đúng (`cost / correct answer`) của v2 lại rẻ hơn hơn 11.7 lần** so với v1 ($0.00003381 so với $0.00039735). Điều này chứng minh rằng chi phí của v1 tuy thấp trên từng request nhưng hầu như lãng phí 95.7% ngân sách vào các câu trả lời sai hoặc vô ích.
- **Về Latency:** v2 có p50 tăng nhẹ từ ~166ms lên ~201ms do tốn thêm bước vector/keyword search trong knowledge base (~20ms) và thời gian giải mã thêm tokens từ LLM. Tuy nhiên mức tăng này hoàn toàn chấp nhận được và vẫn nằm sâu dưới ngưỡng SLO (< 500ms).

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`): `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**: `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~60s (sau `for: 1m`) | Panel **Error rate (% 5xx)** chuyển sang màu đỏ (> 5%) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~120s (sau `for: 2m`) | Panel **p95 Latency** nhảy vọt vượt ngưỡng 1.0s (chuyển đỏ) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~120s (sau `for: 2m`) | Panel **Estimated Cost / Hour** và **Tokens & Cost** vọt lên > $2/h |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~30s (sau `for: 30s`) | Panel **Active Instances** giảm số lượng và trang Prometheus Alerts |
| E | `AGENT_VERSION=v1` | *Không có alert nào firing* | Không xảy ra | Không có panel nào cảnh báo lỗi vì hệ thống vẫn trả HTTP 200 nhanh |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

- Thí nghiệm E là dạng **suy giảm chất lượng âm thầm (Silent Semantic Degradation)**: Hạ tầng (CPU, RAM, HTTP status, latency) hoàn toàn bình thường, nhưng chất lượng nội dung trả lời bị thụt lùi (từ 100% xuống 4.3%).
- Để phát hiện trong production, cần áp dụng các giải pháp **AI Quality Observability & Business Monitoring**:
  1. **Continuous Synthetic Evaluation (Golden Dataset Testing):** Định kỳ (mỗi giờ hoặc sau mỗi deployment) chạy một cronjob gửi 23 câu hỏi golden dataset tới endpoint production và kiểm tra semantic accuracy tự động. Nếu điểm giảm xuống dưới 80%, kích hoạt alert `AgentQualityDegradation`.
  2. **Theo dõi Business Metrics & User Feedback:** Đếm số lượng hành vi của người dùng (tỉ lệ bấm nút Dislike/Thumbs down, tỉ lệ bấm Copy, tỉ lệ bấm Regenerate câu trả lời, độ dài đoạn chat). Nếu tỉ lệ Thumbs-down tăng đột biến vượt ngưỡng 5%, cảnh báo tới đội ngũ product.
  3. **LLM-as-a-judge Sampling:** Lấy mẫu ngẫu nhiên 1% - 5% lượng request thật của người dùng và dùng một LLM đánh giá độc lập (judge) chấm điểm độ phù hợp (relevance score) và tính ảo giác (hallucination score), sau đó xuất metric `llm_eval_score` vào Prometheus để lập alert rule.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được trong Jaeger:

- `trace_id`: `8e63c5fed6b27684801c9a236ec226c5`
- Tổng thời gian: `1704.0 ms`
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1678.3 ms`, `98.5%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T10:02:25.892113+00:00", "level": "INFO", "service": "observable-agent", "instance": "226550ee4ddf", "event": "llm_call", "trace_id": "8e63c5fed6b27684801c9a236ec226c5", "span_id": "966bf225dc8b85b6", "request_id": "1e6a2b72e846", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 83, "output_tokens": 44, "cost_usd": 3.9e-05, "llm_ms": 1677.8}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 57.24 | 210 | 1200 | 1700 | 72 |
| 3 | 59.56 | 200 | 230 | 1700 | 66 |

*(Ghi chú: Bảng trên thống kê chi tiết cho endpoint `POST /ask`. Nếu tính tổng aggregated bao gồm cả probe `/health`, quy mô 1 instance đạt 62.77 req/s với p95 1100ms; quy mô 3 instances đạt 65.80 req/s với p95 230ms).*

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- **Scale có cải thiện p95 không:** **CÓ, CẢI THIỆN RẤT RÕ RỆT.** Khi tăng từ 1 instance lên 3 instances sau Nginx load balancer:
  - Latency **p95 giảm mạnh từ 1200ms xuống chỉ còn 230ms** (giảm hơn 5 lần, đưa hệ thống từ trạng thái vi phạm SLO trở về mức hoàn toàn tuân thủ SLO < 500ms).
  - p50 giảm từ 210ms xuống 200ms.
  - Số lượng lỗi (failures) giảm từ 72 xuống 66.
- **Nút thắt (Bottleneck) nằm ở đâu:**
  - Ở quy mô 1 instance, nút thắt nằm ở **khả năng phục vụ đồng thời của đơn process (Concurrency Limit & Event Loop Queueing)**: Dưới tải 100 users liên tục, hàng trăm request phải xếp hàng chờ trong hàng đợi kết nối của instance duy nhất, làm cho thời gian chờ đợi (waiting time) tăng vọt, đẩy p95 lên 1.2 giây.
  - Khi scale lên 3 instances, Nginx phân phối đều traffic qua cơ chế round-robin, triệt tiêu hoàn toàn độ trễ xếp hàng, đưa p95 về đúng thời gian xử lý thực của mô hình (~230ms).
  - Riêng **p99 vẫn duy trì ở mức ~1700ms ở cả 2 trường hợp**: Điều này là hoàn toàn chính xác theo thiết kế hệ thống, bởi vì mock LLM cố tình tiêm lỗi độ trễ `MOCK_SLOW_RATE=0.03` (3% request bị chậm cố định 1500ms). Nút thắt ở đuôi p99 này nằm ở **độ trễ của dịch vụ LLM thượng nguồn (upstream dependency latency)** — việc scale thêm instance của agent không thể làm tăng tốc thời gian suy luận của LLM provider bên ngoài nếu provider đó bị lag.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Không bao giờ nhìn vào latency trung bình (Average Latency):** Phải luôn đo lường bằng phân vị phần trăm (`p95`, `p99`) vì giá trị trung bình che giấu hoàn toàn trải nghiệm tồi tệ của nhóm người dùng gặp đuôi trễ (tail latency).
  2. **Đo lường toàn diện cả 2 mặt Hiệu năng (Performance) và Chất lượng (Quality):** Deploy lên cloud chỉ mới là bước đầu; hệ thống có thể chạy rất nhanh và trả về mã HTTP 200 nhưng nội dung trả lời lại hoàn toàn sai nếu không có bộ kiểm thử tự động với Golden Dataset (chặn regression trong CI/CD).
  3. **Sức mạnh liên kết của 3 trụ cột Observability:** Metrics (Prometheus/Grafana) giúp phát hiện *khi nào có sự cố*, Traces (OpenTelemetry/Jaeger) chỉ ra chính xác *sự cố nằm ở span/bước nào*, và Logs (Structured JSON) cung cấp ngữ cảnh chi tiết *vì sao sự cố xảy ra* thông qua `trace_id`.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - **Metric bổ sung:**
    - `llm_time_to_first_token_seconds` (TTFT): Đo độ trễ từ lúc gửi request tới khi nhận được token đầu tiên (cực kỳ quan trọng khi streaming response).
    - `llm_context_cache_hit_rate`: Đo tỉ lệ hit prompt caching của các provider (như OpenAI, Anthropic, Gemini) để tối ưu chi phí và độ trễ.
    - `agent_tool_execution_duration_seconds`: Đo latency của từng tool/function calling mà agent kích hoạt.
  - **Alert bổ sung:**
    - `LLMBudgetExhaustionPredictor`: Cảnh báo khi tốc độ chi tiêu dự báo sẽ vượt ngân sách tháng trước ngày thứ 20.
    - `DatabaseConnectionPoolSaturation`: Cảnh báo khi số connection tới Redis/Postgres đạt trên 85% pool size.
    - `UpstreamProviderDegradation`: Cảnh báo khi tỉ lệ lỗi 429/500/503 từ OpenAI/Anthropic vượt quá 2% trong 5 phút.
