import React, { useState } from 'react';
import { useSessionStore } from '../../store/useSessionStore';
import { apiClient } from '../../utils/apiClient';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { setAuth } = useSessionStore();

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      if (mode === 'register') {
        const data = await apiClient('/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            email,
            password,
            full_name: fullName,
            device_fingerprint: 'rolesync_chrome_ext',
          }),
        });
        setAuth(data.user, data.access_token, data.refresh_token);
        onSuccess(`Welcome to RoleSync, ${data.user.full_name}!`);
        onClose();
      } else {
        const data = await apiClient('/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email,
            password,
            device_fingerprint: 'rolesync_chrome_ext',
          }),
        });
        setAuth(data.user, data.access_token, data.refresh_token);
        onSuccess(`Signed in as ${data.user.email}`);
        onClose();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleMock = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient('/auth/google', {
        method: 'POST',
        body: JSON.stringify({
          id_token: 'google_oauth_token_client',
          device_fingerprint: 'rolesync_chrome_ext',
        }),
      });
      setAuth(data.user, data.access_token, data.refresh_token);
      onSuccess(`Signed in with Google as ${data.user.email}`);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Google authentication failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header Tabs */}
        <div className="flex border-b border-slate-100 bg-slate-50/80">
          <button
            onClick={() => { setMode('login'); setErrorMsg(null); }}
            className={`flex-1 py-3 text-xs font-bold transition-colors ${
              mode === 'login'
                ? 'text-indigo-600 bg-white border-b-2 border-indigo-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => { setMode('register'); setErrorMsg(null); }}
            className={`flex-1 py-3 text-xs font-bold transition-colors ${
              mode === 'register'
                ? 'text-indigo-600 bg-white border-b-2 border-indigo-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            Create Account
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-3.5">
          <div className="text-center">
            <h2 className="text-sm font-bold text-slate-900">
              {mode === 'login' ? 'Sign into your RoleSync Vault' : 'Create candidate profile vault'}
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Secure AES-256 envelope encryption with tenant isolation
            </p>
          </div>

          {errorMsg && (
            <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
              {errorMsg}
            </div>
          )}

          {mode === 'register' && (
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">Full Name</label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Alex Mercer"
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
              />
            </div>
          )}

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="candidate@example.com"
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">Password</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors disabled:opacity-50 mt-1 cursor-pointer"
          >
            {isLoading ? 'Processing...' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>

          <div className="relative flex py-1 items-center">
            <div className="grow border-t border-slate-200"></div>
            <span className="shrink mx-2 text-[10px] text-slate-400 uppercase font-semibold">or</span>
            <div className="grow border-t border-slate-200"></div>
          </div>

          <button
            type="button"
            onClick={handleGoogleMock}
            disabled={isLoading}
            className="w-full py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold text-xs rounded-xl transition-colors flex items-center justify-center gap-2 cursor-pointer"
          >
            <span>🌐 Continue with Google</span>
          </button>

          <div className="flex justify-center mt-2">
            <button
              type="button"
              onClick={onClose}
              className="text-[11px] text-slate-500 hover:text-slate-800 font-semibold underline cursor-pointer"
            >
              Continue as Guest / Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

