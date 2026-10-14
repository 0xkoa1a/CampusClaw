const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../app/static/auth.js'), 'utf8');

function harness(identity = false) {
  let logout;
  const requests = [], navigations = [], status = {textContent: ''};
  const storage = new Map([['campusclaw.accessToken', 'public-unit-test-token']]);
  const context = vm.createContext({Headers, AbortController, DOMException,
    sessionStorage: {getItem: k => storage.get(k), removeItem: k => storage.delete(k)},
    window: {location: {assign: url => navigations.push(url)}},
    document: {querySelector: selector => selector === '#logout-form'
      ? {addEventListener: (_, callback) => {logout = callback;}}
      : selector === '#auth-status' && identity ? status : null},
    fetch: (url, options) => new Promise((resolve, reject) => {
      const request = {url, options, resolve, reject}; requests.push(request);
      options.signal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')));
    }),
  });
  vm.runInContext(source, context);
  return {context, requests, navigations, status, storage,
    logout: () => logout({preventDefault() {}})};
}

test('logout aborts the startup identity check and navigates once', async () => {
  const h = harness(true);
  assert.equal(h.requests[0].url, '/api/materials');
  const finished = h.logout();
  assert.equal(h.requests[0].options.signal.aborted, true);
  assert.equal(h.requests[1].url, '/api/logout');
  h.requests[1].resolve({ok: true, status: 200});
  await finished;
  assert.deepEqual(h.navigations, ['/login']);
  assert.equal(h.storage.has('campusclaw.accessToken'), false);
  assert.equal(h.status.textContent, '');
});

test('a pending background 401 cannot trigger another redirect during logout', async () => {
  const h = harness();
  const pending = h.context.window.campusAuth.fetch('/api/agents').then(
    () => {throw Error('pending background response must be discarded');},
    error => assert.equal(error.name, 'AbortError'));
  const finished = h.logout();
  h.requests[0].resolve({ok: false, status: 401});
  await pending;
  h.requests[1].resolve({ok: true, status: 200});
  await finished;
  assert.deepEqual(h.navigations, ['/login']);
  const before = h.requests.length;
  await assert.rejects(h.context.window.campusAuth.fetch('/api/conversations'), {name: 'AbortError'});
  assert.equal(h.requests.length, before);
});

test('failed logout keeps the token and permits a retry', async () => {
  const h = harness();
  const failed = h.logout();
  h.requests[0].resolve({ok: false, status: 503});
  await failed;
  assert.equal(h.storage.has('campusclaw.accessToken'), true);
  assert.deepEqual(h.navigations, []);
  const request = h.context.window.campusAuth.fetch('/api/me');
  h.requests[1].resolve({ok: true, status: 200});
  assert.equal((await request).status, 200);
});

test('ordinary unauthorized requests retain the existing clear-token behavior', async () => {
  const h = harness();
  const request = h.context.window.campusAuth.fetch('/api/me');
  h.requests[0].resolve({ok: false, status: 401});
  assert.equal((await request).status, 401);
  assert.equal(h.storage.has('campusclaw.accessToken'), false);
});
