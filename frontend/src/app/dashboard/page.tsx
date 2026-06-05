'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import api from '@/services/api';
import { 
  Briefcase, 
  FileText, 
  CheckCircle, 
  Clock
} from 'lucide-react';

interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  source: string;
  match_score?: number;
}

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchRecentJobs = async () => {
      try {
        const response = await api.get('/jobs/', { params: { limit: 3 } });
        setRecentJobs(response.data);
      } catch (error) {
        console.error('Failed to fetch recent jobs:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchRecentJobs();
  }, []);

  const stats = [
    { label: 'Total Jobs', value: '128', icon: Briefcase, color: 'text-blue-500' },
    { label: 'Applications', value: '45', icon: FileText, color: 'text-purple-500' },
    { label: 'Interviews', value: '12', icon: CheckCircle, color: 'text-emerald-500' },
    { label: 'Pending', value: '8', icon: Clock, color: 'text-amber-500' },
  ];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-4xl font-black text-zinc-950 tracking-tight">Welcome back, {user?.full_name || 'User'}!</h1>
        <p className="text-zinc-600 font-semibold mt-2">Here's what's happening with your job search today.</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        {stats.map((stat, idx) => (
          <div key={idx} className="bg-white border-2 border-zinc-950 p-6 rounded-3xl hover:translate-y-[-2px] transition-all group shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-xl ${stat.color} bg-opacity-10 bg-current`}>
                <stat.icon size={24} className={stat.color} />
              </div>
              <span className="text-xs font-black text-emerald-600 bg-emerald-50 border border-emerald-250 px-2 py-0.5 rounded-full">+12%</span>
            </div>
            <div className="text-3xl font-black text-zinc-950">{stat.value}</div>
            <div className="text-xs text-zinc-500 font-bold uppercase tracking-wider mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Recent Activity Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
          <h3 className="text-xl font-black text-zinc-950 mb-6 uppercase tracking-tight border-b-2 border-zinc-100 pb-4">Recent Job Matches</h3>
          <div className="space-y-4">
            {isLoading ? (
              <div className="py-10 text-center text-zinc-500 font-semibold">Loading matches...</div>
            ) : recentJobs.length > 0 ? (
              recentJobs.map((job) => (
                <div key={job.id} className="flex items-center justify-between p-5 rounded-2xl border-2 border-zinc-950 hover:bg-zinc-50 transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 rounded-xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
                      <Briefcase size={20} className="text-zinc-600" />
                    </div>
                    <div>
                      <div className="font-bold text-zinc-950 text-base">{job.title}</div>
                      <div className="text-sm text-zinc-500 font-medium">{job.company} • {job.location}</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    {job.match_score && (
                      <span className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold border border-emerald-250">
                        {job.match_score}% Match
                      </span>
                    )}
                    <button className="text-sm text-blue-600 hover:text-blue-800 font-bold hover:underline cursor-pointer">Apply</button>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-10 text-center border-2 border-dashed border-zinc-300 rounded-2xl text-zinc-500 font-bold">
                No recent matches. Explore new jobs in the Jobs section!
              </div>
            )}
          </div>
        </div>

        <div className="bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
          <h3 className="text-xl font-black text-zinc-950 mb-6 uppercase tracking-tight border-b-2 border-zinc-100 pb-4">Agent Status</h3>
          <div className="space-y-6">
            <div className="flex items-center justify-between font-semibold">
              <span className="text-zinc-700">Hermes Agent</span>
              <span className="flex items-center space-x-2 text-emerald-600 text-sm font-bold bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Active</span>
              </span>
            </div>
            <div className="flex items-center justify-between font-semibold">
              <span className="text-zinc-700">TinyFish Scraper</span>
              <span className="text-zinc-500 text-sm font-bold bg-zinc-100 px-3 py-1 rounded-full border border-zinc-200">Idle</span>
            </div>
            <div className="mt-6 p-5 bg-blue-50 border-2 border-blue-200 rounded-2xl">
              <p className="text-sm text-blue-800 font-bold leading-relaxed">
                Hermes is currently analyzing your profile to find the best matches.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
