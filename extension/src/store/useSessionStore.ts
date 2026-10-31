import { create } from 'zustand';
import { JDExtractedPayload } from '../types/messages';

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  planTier: string;
}

export interface SessionState {
  isAuthenticated: boolean;
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  currentJd: JDExtractedPayload | null;
  autofillStatus: 'IDLE' | 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED';

  initAuth: () => Promise<void>;
  setAuth: (user: UserProfile, accessToken: string, refreshToken: string) => void;
  setCurrentJd: (jd: JDExtractedPayload | null) => void;
  setAutofillStatus: (status: 'IDLE' | 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED') => void;
  logout: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  isAuthenticated: false,
  user: null,
  accessToken: null,
  refreshToken: null,
  currentJd: null,
  autofillStatus: 'IDLE',

  initAuth: async () => {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      try {
        const stored = await chrome.storage.local.get('rolesync_auth');
        if (stored?.rolesync_auth?.accessToken) {
          const { user, accessToken, refreshToken } = stored.rolesync_auth;
          set({
            isAuthenticated: true,
            user,
            accessToken,
            refreshToken,
          });
        }
      } catch (e) {
        console.warn('[RoleSync Session] Could not restore auth from storage:', e);
      }
    }
  },

  setAuth: (user, accessToken, refreshToken) => {
    set({
      isAuthenticated: true,
      user,
      accessToken,
      refreshToken,
    });
    // Persist securely to extension local storage
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({
        rolesync_auth: { user, accessToken, refreshToken },
      });
    }
  },

  setCurrentJd: (jd) => {
    set({ currentJd: jd });
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.session) {
      chrome.storage.session.set({ current_jd: { data: jd, updatedAt: Date.now() } });
    }
  },

  setAutofillStatus: (status) => set({ autofillStatus: status }),

  logout: () => {
    set({
      isAuthenticated: false,
      user: null,
      accessToken: null,
      refreshToken: null,
      currentJd: null,
      autofillStatus: 'IDLE',
    });
    if (typeof chrome !== 'undefined' && chrome.storage) {
      chrome.storage.local.remove('rolesync_auth');
      chrome.storage.session.remove('current_jd');
    }
  },
}));
