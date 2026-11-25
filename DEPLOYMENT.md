# Deployment Information

## Public URL
https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app/health
# Expected: {"status": "ok"}
```

### Readiness Check
```bash
curl https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app/ready
# Expected: {"status": "ready"}
```

### API Test (without authentication — Expected 401)
```bash
curl -i -X POST https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### API Test (with authentication — Expected 200)
```bash
curl -i -X POST https://k5-l3a-day14-hoanhdung-2a202603613-deployment-be-production.up.railway.app/ask \
  -H "X-API-Key: secret-prod-key-123" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- `PORT`: 8000
- `ENVIRONMENT`: production
- `AGENT_API_KEY`: secret-prod-key-123
- `REDIS_URL`: ${{Redis.REDIS_URL}}

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
