'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import api from '@/services/api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { access_token } = response.data;

      // Fetch the real user profile
      const userResponse = await api.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`
        }
      });

      const user = userResponse.data;

      setAuth(user, access_token);

      // Set cookie for middleware
      document.cookie = `auth-token=${access_token}; path=/; max-age=1800; samesite=lax`;

      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to login');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 text-zinc-900 p-4">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-3xl border-2 border-zinc-950 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
        <div>
          <h2 className="text-center text-3xl font-black tracking-tight text-zinc-950 uppercase">
            AI Job Automation
          </h2>
          <p className="mt-2 text-center text-sm text-zinc-500 font-semibold">
            Sign in to your account
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-bold text-zinc-800">Email address</label>
              <input
                type="email"
                required
                className="mt-1.5 block w-full px-4 py-3 bg-white border-2 border-zinc-950 rounded-xl outline-none focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-bold text-zinc-800">Password</label>
              <input
                type="password"
                required
                className="mt-1.5 block w-full px-4 py-3 bg-white border-2 border-zinc-950 rounded-xl outline-none focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="text-red-700 text-sm bg-red-50 p-3 rounded-lg border-2 border-red-200 font-bold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
              {error}
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="group relative w-full flex justify-center py-3 px-4 border-2 border-zinc-950 text-sm font-black rounded-xl text-white bg-zinc-900 hover:bg-zinc-800 transition-all shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>

          <div className="text-center">
            <Link href="/register" className="text-sm text-zinc-600 hover:text-zinc-950 font-bold hover:underline transition-all">
              Don't have an account? Register
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
