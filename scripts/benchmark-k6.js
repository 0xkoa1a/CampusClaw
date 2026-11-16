// Intended for the isolated localstub fixture: requests are real loopback
// HTTP, while model and vector providers are deterministic test stubs.
import http from 'k6/http';
import { check, fail } from 'k6';
import { Trend } from 'k6/metrics';

const base = __ENV.CAMPUSCLAW_K6_BASE_URL || 'http://127.0.0.1:18090';
const mode = __ENV.CAMPUSCLAW_K6_MODE || '';
const vus = Number(__ENV.CAMPUSCLAW_K6_VUS || 20);
const duration = __ENV.CAMPUSCLAW_K6_DURATION || '60s';
const username = __ENV.CAMPUSCLAW_K6_USERNAME || 'student_a1';
const password = __ENV.CAMPUSCLAW_K6_PASSWORD || '';
const assignmentId = __ENV.CAMPUSCLAW_K6_ASSIGNMENT_ID || '1';
const query = __ENV.CAMPUSCLAW_K6_QUERY || '方程';
const endpointDuration = new Trend('benchmark_endpoint_duration', true);

function loopbackOnly(value) {
  const match = /^http:\/\/([^/:?#]+)(?::([0-9]+))?$/.exec(value);
  return Boolean(match && (match[1] === 'localhost' || match[1] === '127.0.0.1' || match[1] === '[::1]'));
}

if (!loopbackOnly(base)) fail('CAMPUSCLAW_K6_BASE_URL must be an HTTP loopback origin');
if (!['submit', 'query', 'search'].includes(mode)) fail('CAMPUSCLAW_K6_MODE must be submit, query, or search');
if (!Number.isInteger(vus) || vus < 1 || vus > 200) fail('CAMPUSCLAW_K6_VUS must be an integer from 1 to 200');
if (!/^\d+[smh]$/.test(duration)) fail('CAMPUSCLAW_K6_DURATION must use seconds, minutes, or hours');
if (!password) fail('CAMPUSCLAW_K6_PASSWORD is required');
if (!/^\d+$/.test(assignmentId)) fail('CAMPUSCLAW_K6_ASSIGNMENT_ID must be a positive integer');

export const options = {
  scenarios: { classroom_http: { executor: 'constant-vus', vus, duration } },
  thresholds: { http_req_failed: ['rate<0.01'], checks: ['rate>0.99'] },
};

// 401 is expected only for the explicit post-logout revocation probe; checks
// still require the endpoint and logout statuses to match their contracts.
http.setResponseCallback(http.expectedStatuses(200, 202, 401));

const params = { headers: { Accept: 'application/json' }, timeout: '10s', responseType: 'none' };

export function setup() {
  const response = http.post(`${base}/api/login`, JSON.stringify({ username, password, auth_mode: 'bearer' }), {
    ...params,
    responseType: 'text',
    headers: { ...params.headers, 'Content-Type': 'application/json' },
  });
  let token = '';
  try { token = response.json('access_token') || ''; } catch (_) { /* reported below */ }
  if (response.status !== 200 || !token) fail(`fixture login failed with HTTP ${response.status}`);
  return { token, runId: `${Date.now()}-${Math.random().toString(36).slice(2)}` };
}

export default function (data) {
  const auth = { ...params, headers: { ...params.headers, Authorization: `Bearer ${data.token}` } };
  let response;
  if (mode === 'submit') {
    const key = `k6-${data.runId}-${__VU}-${__ITER}-${Math.random().toString(36).slice(2)}`;
    response = http.post(`${base}/api/assignments/${assignmentId}/submissions`, JSON.stringify({
      content: `Synthetic k6 submission run=${data.runId} vu=${__VU} iteration=${__ITER}`,
    }), { ...auth, headers: { ...auth.headers, 'Content-Type': 'application/json', 'Idempotency-Key': key } });
    check(response, { 'submit accepted (202)': (r) => r.status === 202 });
  } else if (mode === 'query') {
    response = http.get(`${base}/api/tasks`, auth);
    check(response, { 'task query succeeded (200)': (r) => r.status === 200 });
  } else {
    response = http.post(`${base}/api/search`, JSON.stringify({ q: query, mode: 'keyword', limit: 10 }), {
      ...auth, headers: { ...auth.headers, 'Content-Type': 'application/json' },
    });
    check(response, { 'keyword search succeeded (200)': (r) => r.status === 200 });
  }
  endpointDuration.add(response.timings.duration, { mode });
}

export function teardown(data) {
  const response = http.post(`${base}/api/logout`, null, {
    ...params, headers: { ...params.headers, Authorization: `Bearer ${data.token}` },
  });
  check(response, { 'benchmark session revoked (200)': (r) => r.status === 200 });
  const after = http.get(`${base}/api/tasks`, {
    ...params, headers: { ...params.headers, Authorization: `Bearer ${data.token}` },
  });
  check(after, { 'revoked token rejected (401)': (r) => r.status === 401 });
}
