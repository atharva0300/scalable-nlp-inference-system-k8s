import http from 'k6/http';

export let options = {
  scenarios: {
    test: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 20,
    },
  },
};

export default function () {
  http.post('http://localhost:8000/bert', JSON.stringify({
    text: "Amazing product"
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
}
