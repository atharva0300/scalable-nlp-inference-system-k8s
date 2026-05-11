import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    vus: 100,
    duration: '60s',
};

const setupPayload = JSON.stringify({ mode: "static" });

export function setup() {
    // Set cluster routing mode to static before test
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
        'used static routing': (r) => r.json('routing_mode') === 'static',
    });
    sleep(0.05);
}
