import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    // Stage-based queue pressure
    stages: [
        { duration: '30s', target: 50 },  // Ramp up to 50 users
        { duration: '1m', target: 200 },  // Spike to 200 users to overwhelm queues
        { duration: '30s', target: 0 },   // Ramp down
    ],
};

const setupPayload = JSON.stringify({ mode: "adaptive" });

export function setup() {
    http.post('http://127.0.0.1:8000/routing-mode', setupPayload, {
        headers: { 'Content-Type': 'application/json' }
    });
}

export default function () {
    const payload = JSON.stringify({ text: "Test payload", model: "auto" });
    const params = { headers: { 'Content-Type': 'application/json' } };
    
    const res = http.post('http://127.0.0.1:8000/toxicity', payload, params);
    
    check(res, {
        'is status 200': (r) => r.status === 200,
    });
    
    // Very fast ping to build up queue depth rapidly
    sleep(0.01);
}
