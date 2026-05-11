import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    vus: 100,
    duration: '60s',
    thresholds: {
        http_req_duration: ['p(95)<10000'], // 95% of requests should be below 10s under load
        http_req_failed: ['rate<0.15'],     // Errors should be less than 15%
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
    
    // Simulating sustained load with 100 concurrent Virtual Users
    const res = http.post(url, payload, params);
    
    check(res, {
        'is status 200': (r) => r.status === 200,
        'has valid routing': (r) => r.json('routing') !== undefined,
    });
    
    sleep(0.1);
}
