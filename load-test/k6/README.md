# Distributed NLP Inference Load Testing (k6)

## Why Sustained Concurrency Matters

When testing asynchronous Python architectures (like FastAPI), naive load generation tools often attempt "uncontrolled async fanout"—trying to open thousands of sockets simultaneously. 

On Windows, this immediately triggers `ValueError: too many file descriptors in select()`. In production, it causes catastrophic socket exhaustion and networking failures rather than genuinely testing your machine learning models.

**Total Requests ≠ Concurrent Requests**
A realistic load test might execute 10,000 *total requests*, but it should only ever maintain a controlled window of active sockets (e.g., 100 *concurrent requests*) to simulate 100 actual users repeatedly interacting with the platform.

### k6 Integration
`k6` solves this by spinning up **Virtual Users (VUs)**. Each VU executes a request, waits for a response, and then fires the next one, reusing connections via Keep-Alive (unless explicitly disabled). This generates a massive, realistic, **sustained queue pressure** that accurately exercises:
- FastAPI's internal `anyio` thread limits.
- The Adaptive Latency-Aware Router's circuit breakers.
- Kubernetes Horizontal Pod Autoscaler (HPA) queue build-up.

## How to Run

Make sure your `kubectl port-forward svc/fastapi-router-service 8000:8000` is running in a separate terminal.

Then, execute any of the following tests:

```bash
# 50 Concurrent Users | 30 Seconds
k6 run load-test/k6/baseline.js

# 100 Concurrent Users | 60 Seconds
k6 run load-test/k6/moderate.js

# 150 Concurrent Users | 120 Seconds (Will trigger HPA & Circuit Breakers)
k6 run load-test/k6/stress.js
```
