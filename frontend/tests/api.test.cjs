// Run with node --test frontend/tests/api.test.cjs; no package installation needed.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const frontend = path.resolve(__dirname, '..');
function browser(hostname = 'localhost', origin = 'http://localhost:5500', config) {
  const stored = new Map([['authToken', 'synthetic-token']]);
  const context = vm.createContext({
    window: { location: { hostname, origin }, HR_OS_CONFIG: config },
    localStorage: {
      getItem: key => stored.get(key) || null,
      removeItem: key => stored.delete(key),
    },
  });
  for (const file of ['config.js', 'api.js']) {
    vm.runInContext(fs.readFileSync(path.join(frontend, file), 'utf8'), context);
  }
  return context;
}

test('API config supports local, same-origin and separate deployments', () => {
  assert.equal(browser().window.API_BASE, 'http://127.0.0.1:8000/api/v1');
  assert.equal(browser('hr.example.invalid', 'https://hr.example.invalid').window.API_BASE,
    'https://hr.example.invalid/api/v1');
  assert.equal(browser('hr.example.invalid', 'https://hr.example.invalid',
    { apiBase: 'https://api.example.invalid/api/v1/' }).window.API_BASE,
    'https://api.example.invalid/api/v1');
});

test('auth behavior preserves headers, 401 redirect and non-401 responses', () => {
  const context = browser();
  assert.equal(context.getAuthToken(), 'synthetic-token');
  assert.equal(context.authHeaders('synthetic-token').Authorization, 'Bearer synthetic-token');
  assert.equal(context.authHeaders('synthetic-token')['Content-Type'], undefined);
  assert.equal(context.authHeaders('synthetic-token', true)['Content-Type'], 'application/json');
  assert.equal(context.handleUnauthorized({ status: 400 }), false);
  assert.equal(context.getAuthToken(), 'synthetic-token');
  assert.equal(context.handleUnauthorized({ status: 401 }), true);
  assert.equal(context.getAuthToken(), null);
  assert.equal(context.window.location.href, 'login.html');
});

test('API validation errors include field details', () => {
  const context = browser();
  assert.equal(context.describeApiError({ detail: 'Blocked' }), 'Blocked');
  assert.equal(context.describeApiError({ email: ['Invalid email.'] }), 'email: Invalid email.');
  assert.equal(context.describeApiError(null), '');
});

test('every page loads shared API config first and all scripts parse', () => {
  for (const file of fs.readdirSync(frontend).filter(file => file.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(frontend, file), 'utf8');
    const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
    const sources = scripts.map(match => /src="([^"]+)"/.exec(match[1])?.[1]);
    assert.equal(sources[0]?.split('?')[0], 'config.js', file);
    assert.equal(sources[1]?.split('?')[0], 'api.js', file);
    for (const match of scripts) {
      const source = /src="([^"]+)"/.exec(match[1])?.[1];
      const code = source && !source.startsWith('http')
        ? fs.readFileSync(path.join(frontend, source.split('?')[0]), 'utf8') : match[2];
      new vm.Script(code, { filename: file + (source ? ':' + source : ':inline') });
    }
    assert.doesNotMatch(html, /API_BASE_PUBLIC|16\.170\.98\.44/, file);
  }
});
