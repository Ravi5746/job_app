'use client';

import { useAuthStore } from '@/store/authStore';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { 
  LayoutDashboard, 
  Briefcase, 
  FileText, 
  Settings, 
  LogOut,
  Plus,
  Search,
  Sparkles,
  Bookmark
} from 'lucide-react';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, logout } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = () => {
    logout();
    document.cookie = 'auth-token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;';
    router.push('/login');
  };

  const navItems = [
    { label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
    { label: 'Jobs', icon: Briefcase, href: '/dashboard/jobs' },
    { label: 'Saved Jobs', icon: Bookmark, href: '/dashboard/saved-jobs' },
    { label: 'Resumes', icon: FileText, href: '/dashboard/resumes' },
    { label: 'Optimizer', icon: Sparkles, href: '/dashboard/resumes/optimizer' },
    { label: 'Settings', icon: Settings, href: '/dashboard/settings' },
  ];

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 flex">
      {/* Sidebar */}
      <aside className="w-64 border-r-2 border-zinc-950 bg-white hidden md:flex flex-col fixed inset-y-0 z-20">
        <div className="p-6 border-b-2 border-zinc-950">
          <h2 className="text-2xl font-black tracking-tight text-zinc-950 uppercase">
            AI Platform
          </h2>
        </div>
        
        <nav className="flex-1 px-4 space-y-3 mt-6">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link 
                key={item.href}
                href={item.href} 
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all border-2 ${
                  isActive 
                    ? 'bg-zinc-900 text-white border-zinc-900 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]' 
                    : 'text-zinc-600 border-transparent hover:bg-zinc-100 hover:text-zinc-900'
                }`}
              >
                <item.icon size={20} className={isActive ? 'text-white' : 'text-zinc-500'} />
                <span className="font-bold text-sm">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t-2 border-zinc-950 bg-zinc-50">
          <button 
            onClick={handleLogout}
            className="flex items-center space-x-3 px-4 py-3 w-full rounded-xl text-zinc-600 hover:bg-red-50 hover:text-red-600 border border-transparent hover:border-red-200 transition-all"
          >
            <LogOut size={20} />
            <span className="font-bold text-sm">Logout</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col md:pl-64">
        {/* Header */}
        <header className="h-20 border-b-2 border-zinc-950 flex items-center justify-between px-8 bg-white sticky top-0 z-10">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
            <input 
              type="text" 
              placeholder="Search jobs, applications..."
              className="w-full bg-white border-2 border-zinc-950 rounded-xl py-2.5 pl-10 pr-4 text-zinc-900 placeholder:text-zinc-400 outline-none focus:ring-0 focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
            />
          </div>
          
          <div className="flex items-center space-x-4">
            <button className="bg-zinc-900 hover:bg-zinc-800 text-white px-5 py-2.5 rounded-xl flex items-center space-x-2 transition-all border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] font-bold text-sm cursor-pointer">
              <Plus size={18} />
              <span>New Job</span>
            </button>
            <div className="w-10 h-10 rounded-full bg-zinc-900 text-white border-2 border-zinc-950 flex items-center justify-center font-black text-sm shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
              {user?.full_name?.charAt(0) || 'U'}
            </div>
          </div>
        </header>

        {/* Dynamic Content */}
        <main className="flex-1 bg-zinc-50">
          {children}
        </main>
      </div>
    </div>
  );
}
