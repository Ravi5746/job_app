'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';

export default function Navbar() {
  const pathname = usePathname();

  const linkClass = (path: string) =>
    `px-4 py-2 rounded-md ${pathname === path ? 'bg-zinc-900 text-white' : 'text-zinc-900 hover:bg-zinc-200'}`;

  return (
    <nav className="flex space-x-4 mb-6 border-b-2 border-zinc-950 pb-2">
      <Link href="/dashboard/jobs" className={linkClass('/dashboard/jobs')}>
        Jobs
      </Link>
      <Link href="/settings/profile" className={linkClass('/settings/profile')}>
        Profile Settings
      </Link>
    </nav>
  );
}
