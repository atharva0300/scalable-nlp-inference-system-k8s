import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    vus: 50,
    duration: '30s',
    thresholds: {
        http_req_duration: ['p(95)<5000'], // 95% of requests should be below 5s
        http_req_failed: ['rate<0.1'],     // Errors should be less than 10%
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
    // Port forward URL
    const url = 'http://127.0.0.1:8000/toxicity';
    
    // K6 inherently reuses HTTP connections (Keep-Alive) unless told otherwise. 
    // This allows realistic sustained pressure testing.
    const res = http.post(url, payload, params);
    
    check(res, {
        'is status 200': (r) => r.status === 200,
        'has valid routing': (r) => r.json('routing') !== undefined,
    });
    
    // Add small sleep to simulate human wait / real client interval,
    // though here we keep it extremely short to maintain high inference pressure
    sleep(0.1);
}
