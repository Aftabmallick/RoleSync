import { useSessionStore } from '../store/useSessionStore';

export const API_BASE_URL = 'http://localhost:8000/api/v1';

// Mutex promise to prevent concurrent refresh races across multiple requests
let refreshPromise: Promise<string | null> | null = null;

async function executeTokenRefresh(): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const store = useSessionStore.getState();
      if (!store.refreshToken) return null;

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
        return tokenData.access_token as string;
      } else {
        // Refresh token revoked or invalid
        store.logout();
        return null;
      }
    } catch (err) {
      console.warn('[RoleSync API] Automatic token refresh failed:', err);
      useSessionStore.getState().logout();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export class RoleSyncApiError extends Error {
  public status: number;
  public title?: string;
  public detail?: string;
  public type?: string;
  public invalid_params?: Array<{ name: string; reason: string }>;

  constructor(status: number, message: string, rfcProblem?: any) {
    super(message);
    this.name = 'RoleSyncApiError';
    this.status = status;
    if (rfcProblem && typeof rfcProblem === 'object') {
      this.title = rfcProblem.title;
      this.detail = rfcProblem.detail;
      this.type = rfcProblem.type;
      this.invalid_params = rfcProblem.invalid_params;
    }
  }
}

/**
 * Universal authenticated API client for RoleSync Chrome Extension.
 * - Automatically injects RS256 Bearer access token from SessionStore.
 * - Automatically performs Refresh Token Rotation (RTR) on 401 Unauthorized via mutex.
 * - Retries original request with newly issued credentials.
 * - Cleans up session state on revoked/invalid refresh tokens.
 * - Parses RFC 7807 problem details into RoleSyncApiError.
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

  // Handle Token Expiry & Automatic Refresh Rotation via Mutex
  if (response.status === 401 && store.refreshToken) {
    const newAccessToken = await executeTokenRefresh();
    if (newAccessToken) {
      headers.set('Authorization', `Bearer ${newAccessToken}`);
      response = await fetch(url, {
        ...options,
        headers,
      });
    }
  }

  if (!response.ok) {
    let errorDetail = response.statusText;
    let rfcData: any = null;
    try {
      rfcData = await response.json();
      errorDetail = rfcData.detail || rfcData.title || JSON.stringify(rfcData);
    } catch {
      // response is not json
    }
    throw new RoleSyncApiError(response.status, `[HTTP ${response.status}] ${errorDetail}`, rfcData);
  }

  // For 204 No Content
  if (response.status === 204) {
    return null as unknown as T;
  }

  return response.json();
}

/**
 * Native Fetch drop-in replacement that automatically injects the active Bearer token
 * and handles 401 token refresh via the singleton mutex.
 */
export async function fetchWithAuth(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const store = useSessionStore.getState();
  const headers = new Headers(init?.headers || {});
  if (store.accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${store.accessToken}`);
  }

  let response = await fetch(input, { ...init, headers });

  if (response.status === 401 && store.refreshToken) {
    const newAccessToken = await executeTokenRefresh();
    if (newAccessToken) {
      headers.set('Authorization', `Bearer ${newAccessToken}`);
      response = await fetch(input, { ...init, headers });
    }
  }

  return response;
}
