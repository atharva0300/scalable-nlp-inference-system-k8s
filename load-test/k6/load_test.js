import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 5 },  // Low load -> should trigger Mistral
    { duration: '30s', target: 15 }, // Medium load -> should trigger Phi-3
    { duration: '1m', target: 50 },  // High load spike -> should trigger TinyLlama
    { duration: '30s', target: 0 },  // Cool down
  ],
};

export default function () {
  const url = 'http://localhost:30080/generate'; // Pointing to NGINX NodePort
  
  const payload = JSON.stringify({
    prompt: 'Summarize the impact of AI on performance engineering in 5 words.'
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post(url, payload, params);
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 10s': (r) => r.timings.duration < 10000,
  });

  sleep(1); // Think time between requests
}
