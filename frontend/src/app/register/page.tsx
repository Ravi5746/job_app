'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api from '@/services/api';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      setIsLoading(false);
      return;
    }

    try {
      await api.post('/auth/register', {
        email,
        password,
        full_name: fullName,
      });

      router.push('/login?registered=true');
    } catch (err: any) {
      console.error('Registration error:', err);
      const detail = err.response?.data?.detail;
      const type = err.response?.data?.type;
      
      if (detail) {
        setError(detail);
      } else if (type) {
        setError(`Server error: ${type}`);
      } else {
        setError('Failed to connect to server. Please check if the backend is running.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 text-zinc-900 p-4">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-3xl border-2 border-zinc-950 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
        <div>
          <h2 className="text-center text-3xl font-black tracking-tight text-zinc-950 uppercase">
            Create Account
          </h2>
          <p className="mt-2 text-center text-sm text-zinc-500 font-semibold">
            Join the AI Job Automation Platform
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-bold text-zinc-800">Full Name</label>
              <input
                type="text"
                required
                className="mt-1.5 block w-full px-4 py-3 bg-white border-2 border-zinc-950 rounded-xl outline-none focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
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
            <div>
              <label className="text-sm font-bold text-zinc-800">Confirm Password</label>
              <input
                type="password"
                required
                className="mt-1.5 block w-full px-4 py-3 bg-white border-2 border-zinc-950 rounded-xl outline-none focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
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
              {isLoading ? 'Creating account...' : 'Sign up'}
            </button>
          </div>

          <div className="text-center">
            <Link href="/login" className="text-sm text-zinc-600 hover:text-zinc-950 font-bold hover:underline transition-colors">
              Already have an account? Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
