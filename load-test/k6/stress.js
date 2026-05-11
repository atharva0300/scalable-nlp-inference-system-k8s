import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    vus: 150,
    duration: '120s',
    thresholds: {
        http_req_duration: ['p(95)<15000'], // Expecting heavy queueing, latency might exceed 15s
        http_req_failed: ['rate<0.30'],     // Some circuit breaker timeouts are expected
    },
};

const payload = JSON.stringify({
    text: "“I could kill you for deleting my files,” he joked during the cybersecurity workshop, while the lecturer explained why toxic language detection systems often misclassify sarcastic or quoted threats as genuine abuse.",
    model: "adaptive"
});

const params = {
    headers: {
        'Content-Type': 'application/json',
    },
};

export default function () {
    const url = 'http://127.0.0.1:8000/toxicity';
    
    // High-pressure stress test to trigger Kubernetes HPA and Adaptive Routing Circuit Breakers
    const res = http.post(url, payload, params);
    
    check(res, {
        'is status 200': (r) => r.status === 200,
        'has valid routing': (r) => r.json('routing') !== undefined,
    });
    
    sleep(0.05); // Barely any sleep, maximum sustainable concurrency pressure
}
