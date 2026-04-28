import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 50 }, // Ramp up to 50 concurrent users
    { duration: '20s', target: 100 }, // Peak at 100 concurrent users
    { duration: '10s', target: 0 },   // Ramp down
  ],
};

export default function () {
  const url = 'http://fastapi-service:8000/generate';
  const payload = JSON.stringify({
    prompt: 'who is the president of india?',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post(url, payload, params);
  
  check(res, {
    'is status 200': (r) => r.status === 200,
  });
  
  sleep(1);
}
