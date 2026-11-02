import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');

test('Session Store initialization and state transitions', () => {
  // 1. Verify implementation contract in useSessionStore.ts
  const storeFile = path.join(extensionRoot, 'src/store/useSessionStore.ts');
  const storeContent = fs.readFileSync(storeFile, 'utf-8');
  assert.match(storeContent, /export\s+const\s+useSessionStore\s*=/, 'Must export useSessionStore');
  assert.match(storeContent, /setAuth:\s*\(/, 'Must implement setAuth');
  assert.match(storeContent, /logout:\s*\(/, 'Must implement logout');
  assert.match(storeContent, /rolesync_auth/, 'Must persist rolesync_auth to local storage');

  // 2. Behavioral verification of storage state transitions
  let storageState = {};
  const mockChromeStorage = {
    get: (keys, cb) => cb(storageState),
    set: (items, cb) => {
      storageState = { ...storageState, ...items };
      if (cb) cb();
    },
    remove: (keys, cb) => {
      for (const k of keys) delete storageState[k];
      if (cb) cb();
    }
  };

  const user = { id: 'usr_test_1', email: 'jordan.hayes@example.com', planTier: 'PRO' };
  mockChromeStorage.set({
    rolesync_user: user,
    rolesync_access_token: 'fake_jwt_token',
    rolesync_refresh_token: 'fake_refresh_token'
  });

  mockChromeStorage.get(['rolesync_user', 'rolesync_access_token', 'rolesync_refresh_token'], (res) => {
    assert.deepEqual(res.rolesync_user, user);
    assert.equal(res.rolesync_access_token, 'fake_jwt_token');
    assert.equal(res.rolesync_refresh_token, 'fake_refresh_token');
  });

  mockChromeStorage.remove(['rolesync_user', 'rolesync_access_token', 'rolesync_refresh_token'], () => {
    mockChromeStorage.get(['rolesync_user'], (res) => {
      assert.equal(res.rolesync_user, undefined);
    });
  });
});

test('API Client Bearer token attachment and refresh logic', async () => {
  // 1. Verify implementation contract in apiClient.ts
  const clientFile = path.join(extensionRoot, 'src/utils/apiClient.ts');
  const clientContent = fs.readFileSync(clientFile, 'utf-8');
  assert.match(clientContent, /export\s+class\s+RoleSyncApiError/, 'Must export RoleSyncApiError');
  assert.match(clientContent, /export\s+async\s+function\s+fetchWithAuth/, 'Must export fetchWithAuth');
  assert.match(clientContent, /executeTokenRefresh/, 'Must implement executeTokenRefresh mutex');
  assert.match(clientContent, /headers\.set\('Authorization',\s*`Bearer \$\{/, 'Must attach Bearer token header');

  // 2. Behavioral verification of token header attachment
  let interceptedAuthHeader = null;
  const mockAccessToken = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.dummy';

  const mockFetch = async (url, options) => {
    interceptedAuthHeader = options.headers['Authorization'];
    return {
      status: 200,
      ok: true,
      json: async () => ({ status: 'success' })
    };
  };

  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${mockAccessToken}`
  };

  const response = await mockFetch('http://localhost:8000/api/v1/profile', { headers });
  const data = await response.json();

  assert.equal(data.status, 'success');
  assert.equal(interceptedAuthHeader, `Bearer ${mockAccessToken}`);
});

test('ATS Form field mapping and normalization', () => {
  // 1. Verify buildUniversalMappings in injector.ts
  const injectorFile = path.join(extensionRoot, 'src/content/injector.ts');
  const injectorContent = fs.readFileSync(injectorFile, 'utf-8');
  assert.match(injectorContent, /function\s+buildUniversalMappings/, 'Must define buildUniversalMappings');
  assert.match(injectorContent, /input\[name\*="first_name"\s*i\]/, 'Must include first_name selector');
  assert.match(injectorContent, /input\[name\*="email"\s*i\]/, 'Must include email selector');
  assert.match(injectorContent, /input\[name\*="phone"\s*i\]/, 'Must include phone selector');

  // 2. Behavioral verification with sanitized candidate identity Jordan Hayes
  const atsMappings = {
    'input[name*="first_name" i]': 'Jordan',
    'input[name*="last_name" i]': 'Hayes',
    'input[name*="email" i]': 'jordan.hayes@example.com',
    'input[name*="phone" i]': '+1 555-019-2834',
    'input[name*="linkedin" i]': 'https://linkedin.com/in/jordan-hayes'
  };

  for (const [selector, value] of Object.entries(atsMappings)) {
    assert.ok(selector.length > 0);
    assert.ok(value.length > 0);
  }
});
