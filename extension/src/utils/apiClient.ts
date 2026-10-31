import { useSessionStore } from '../store/useSessionStore';

export const API_BASE_URL = 'http://localhost:8000/api/v1';

/**
 * Universal authenticated API client for RoleSync Chrome Extension.
 * - Automatically injects RS256 Bearer access token from SessionStore.
 * - Automatically performs Refresh Token Rotation (RTR) on 401 Unauthorized.
 * - Retries original request with newly issued credentials.
 * - Cleans up session state on revoked/invalid refresh tokens.
 */
export async function apiClient<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  const store = useSessionStore.getState();

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Attach access token if present
  if (store.accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${store.accessToken}`);
  }

  let response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle Token Expiry & Automatic Refresh Rotation
  if (response.status === 401 && store.refreshToken) {
    try {
      const refreshRes = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          refresh_token: store.refreshToken,
          device_fingerprint: 'rolesync_chrome_extension',
          email: store.user?.email,
          tier: store.user?.planTier || 'FREE',
        }),
      });

      if (refreshRes.ok) {
        const tokenData = await refreshRes.json();
        if (store.user) {
          store.setAuth(store.user, tokenData.access_token, tokenData.refresh_token);
        }

        // Retry original request with newly minted token
        headers.set('Authorization', `Bearer ${tokenData.access_token}`);
        response = await fetch(url, {
          ...options,
          headers,
        });
      } else {
        // Refresh token revoked or invalid
        store.logout();
      }
    } catch (err) {
      console.warn('[RoleSync API] Automatic token refresh failed:', err);
      store.logout();
    }
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.title || JSON.stringify(errorJson);
    } catch {
      // response is not json
    }
    throw new Error(`[HTTP ${response.status}] ${errorDetail}`);
  }

  // For 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  return response.json();
}

/**
 * Native Fetch drop-in replacement that automatically injects the active Bearer token.
 */
export async function fetchWithAuth(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const store = useSessionStore.getState();
  const headers = new Headers(init?.headers || {});
  if (store.accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${store.accessToken}`);
  }
  return fetch(input, { ...init, headers });
}
