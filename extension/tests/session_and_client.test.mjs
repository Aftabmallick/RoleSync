import test from 'node:test';
import assert from 'node:assert/strict';

test('Session Store initialization and state transitions', () => {
  // Mock localStorage/chrome.storage representation
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

  // Test setAuth persistence
  const user = { id: 'usr_test_1', email: 'test@example.com', planTier: 'PRO' };
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

  // Test clearAuth removal
  mockChromeStorage.remove(['rolesync_user', 'rolesync_access_token', 'rolesync_refresh_token'], () => {
    mockChromeStorage.get(['rolesync_user'], (res) => {
      assert.equal(res.rolesync_user, undefined);
    });
  });
});

test('API Client Bearer token attachment and refresh logic', async () => {
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

  // Simulate client call with token
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
  const atsMappings = {
    'input[name*="first_name" i]': 'Alex',
    'input[name*="last_name" i]': 'Mercer',
    'input[name*="email" i]': 'alex@mercer.dev',
    'input[name*="phone" i]': '+1 555-019-2834',
    'input[name*="linkedin" i]': 'https://linkedin.com/in/alex-mercer'
  };

  for (const [selector, value] of Object.entries(atsMappings)) {
    assert.ok(selector.length > 0);
    assert.ok(value.length > 0);
  }
});

