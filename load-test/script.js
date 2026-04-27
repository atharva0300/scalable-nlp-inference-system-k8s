import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 }, // Ramp up to 20 users
    { duration: '1m', target: 50 },  // Spike to 50 users (triggers tinyllama routing)
    { duration: '30s', target: 0 },  // Ramp down
  ],
};

export default function () {
  const url = 'http://localhost:30080/generate';
  const payload = JSON.stringify({
    prompt: 'Explain load testing in one sentence.',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '300s',
  };

  const res = http.post(url, payload, params);
  
  check(res, {
    'is status 200': (r) => r.status === 200,
    'has response text': (r) => JSON.parse(r.body).response !== undefined,
  });
  
  sleep(1);
}
