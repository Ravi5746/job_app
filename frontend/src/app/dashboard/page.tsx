'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import api from '@/services/api';
import {
  Briefcase,
  FileText,
  CheckCircle,
  Clock,
  User as UserIcon,
  Mail,
  Phone,
  MapPin,
  Code,
  Link,
  Globe,
  Award,
  BookOpen,
  GraduationCap,
  Database
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
  const [fullUser, setFullUser] = useState<any>(user);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fieldStats, setFieldStats] = useState<any[]>([]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        // Fetch detailed user profile
        const userRes = await api.get('/users/me');
        setFullUser(userRes.data);

        // Fetch recent jobs
        const jobsRes = await api.get('/jobs/', { params: { limit: 3 } });
        setRecentJobs(jobsRes.data);

        // Fetch field extraction stats
        const statsRes = await api.get('/extraction/stats');
        setFieldStats(statsRes.data);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDashboardData();
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
        <h1 className="text-4xl font-black text-zinc-950 tracking-tight">Welcome back, {fullUser?.full_name || 'User'}!</h1>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Detailed Profile */}
        <div className="lg:col-span-1 space-y-8">
          <div className="bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <div className="flex items-center space-x-4 mb-6">
              <div className="w-16 h-16 rounded-full bg-blue-100 border-2 border-zinc-950 flex items-center justify-center text-blue-600">
                <UserIcon size={32} />
              </div>
              <div>
                <h3 className="text-xl font-black text-zinc-950">{fullUser?.full_name || 'User'}</h3>
                <p className="text-sm font-bold text-zinc-500">{fullUser?.desired_job_titles?.[0] || 'Job Seeker'}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center space-x-3 text-zinc-700 font-medium">
                <Mail size={18} className="text-zinc-400" />
                <span className="truncate">{fullUser?.email}</span>
              </div>
              {fullUser?.phone && (
                <div className="flex items-center space-x-3 text-zinc-700 font-medium">
                  <Phone size={18} className="text-zinc-400" />
                  <span>{fullUser.phone_country_code} {fullUser.phone}</span>
                </div>
              )}
              {fullUser?.location && (
                <div className="flex items-center space-x-3 text-zinc-700 font-medium">
                  <MapPin size={18} className="text-zinc-400" />
                  <span>{fullUser.location}</span>
                </div>
              )}
              {fullUser?.linkedin_url && (
                <div className="flex items-center space-x-3 text-zinc-700 font-medium">
                  <Link size={18} className="text-blue-500" />
                  <a href={fullUser.linkedin_url} target="_blank" rel="noreferrer" className="hover:underline truncate">{fullUser.linkedin_url}</a>
                </div>
              )}
              {fullUser?.github_url && (
                <div className="flex items-center space-x-3 text-zinc-700 font-medium">
                  <Code size={18} className="text-zinc-950" />
                  <a href={fullUser.github_url} target="_blank" rel="noreferrer" className="hover:underline truncate">{fullUser.github_url}</a>
                </div>
              )}
            </div>

            {fullUser?.skills && fullUser.skills.length > 0 && (
              <div className="mt-8 border-t-2 border-zinc-100 pt-6">
                <h4 className="text-sm font-black text-zinc-950 mb-4 uppercase tracking-wider">Top Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {fullUser.skills.slice(0, 10).map((skill: string, idx: number) => (
                    <span key={idx} className="px-3 py-1 bg-zinc-100 border border-zinc-200 rounded-full text-xs font-bold text-zinc-700">
                      {skill}
                    </span>
                  ))}
                  {fullUser.skills.length > 10 && (
                    <span className="px-3 py-1 bg-zinc-50 border border-zinc-200 rounded-full text-xs font-bold text-zinc-500">
                      +{fullUser.skills.length - 10} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {fullUser?.total_years_experience !== undefined && fullUser.total_years_experience !== null && (
              <div className="mt-6 border-t-2 border-zinc-100 pt-6">
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-zinc-700 text-sm">Total Experience</span>
                  <span className="text-zinc-950 font-black">{fullUser.total_years_experience} Years</span>
                </div>
              </div>
            )}
          </div>

          {/* Agent Status Moved Here */}
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
            </div>
          </div>
        </div>

        {/* Right Column: Recent Activity & Experience */}
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
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

          {/* Work Experience */}
          {fullUser?.work_experience && fullUser.work_experience.length > 0 && (
            <div className="bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
              <div className="flex items-center space-x-3 mb-6 border-b-2 border-zinc-100 pb-4">
                <Briefcase size={24} className="text-zinc-950" />
                <h3 className="text-xl font-black text-zinc-950 uppercase tracking-tight">Work Experience</h3>
              </div>
              <div className="space-y-6">
                {fullUser.work_experience.map((exp: any, idx: number) => (
                  <div key={idx} className="relative pl-6 border-l-2 border-zinc-200">
                    <div className="absolute w-3 h-3 bg-zinc-950 rounded-full -left-[7px] top-1.5"></div>
                    <h4 className="text-lg font-black text-zinc-950">{exp.role}</h4>
                    <div className="text-sm font-bold text-zinc-600 mt-1">{exp.company}</div>
                    <div className="text-xs font-semibold text-zinc-400 mt-1 uppercase tracking-wider">
                      {exp.start || 'Unknown'} - {exp.end || 'Present'}
                    </div>
                    {exp.description && (
                      <p className="mt-3 text-sm text-zinc-600 leading-relaxed font-medium">
                        {exp.description.length > 200 ? exp.description.substring(0, 200) + '...' : exp.description}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Education */}
          {fullUser?.education && fullUser.education.length > 0 && (
            <div className="bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
              <div className="flex items-center space-x-3 mb-6 border-b-2 border-zinc-100 pb-4">
                <GraduationCap size={24} className="text-zinc-950" />
                <h3 className="text-xl font-black text-zinc-950 uppercase tracking-tight">ed</h3>
              </div>
              <div className="space-y-6">
                {fullUser.education.map((edu: any, idx: number) => (
                  <div key={idx} className="flex items-start space-x-4">
                    <div className="w-10 h-10 rounded-lg bg-purple-100 border border-purple-200 flex items-center justify-center flex-shrink-0 mt-1">
                      <BookOpen size={18} className="text-purple-600" />
                    </div>
                    <div>
                      <h4 className="text-md font-black text-zinc-950">{edu.degree} {edu.field ? `in ${edu.field}` : ''}</h4>
                      <div className="text-sm font-bold text-zinc-600 mt-1">{edu.institution}</div>
                      {edu.year && <div className="text-xs font-semibold text-zinc-400 mt-1">{edu.year}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Field Extraction Analytics Section */}
      <div className="mt-10 bg-white border-2 border-zinc-950 rounded-[2rem] p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex items-center space-x-3 mb-6 border-b-2 border-zinc-100 pb-4">
          <Database size={24} className="text-zinc-950" />
          <h3 className="text-xl font-black text-zinc-950 uppercase tracking-tight">Extracted Field Frequency Analytics</h3>
        </div>
        
        {fieldStats && fieldStats.length > 0 ? (
          <div className="overflow-hidden border-2 border-zinc-950 rounded-2xl shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-zinc-800 font-medium">
                <thead>
                  <tr className="bg-zinc-50 border-b-2 border-zinc-950">
                    <th className="p-4 font-black text-zinc-950 uppercase tracking-wider text-xs">Canonical Name</th>
                    <th className="p-4 font-black text-zinc-950 uppercase tracking-wider text-xs">Field Type</th>
                    <th className="p-4 font-black text-zinc-950 uppercase tracking-wider text-xs">Requirement</th>
                    <th className="p-4 font-black text-zinc-950 uppercase tracking-wider text-xs">ATS Platform</th>
                    <th className="p-4 font-black text-zinc-950 uppercase tracking-wider text-xs">Company Context</th>
                    <th className="p-4 font-black text-zinc-950 uppercase tracking-wider text-xs text-right">Occurrences</th>
                  </tr>
                </thead>
                <tbody>
                  {fieldStats.map((stat) => (
                    <tr key={stat.id} className="border-b border-zinc-150 last:border-0 hover:bg-zinc-50 transition-colors">
                      <td className="p-4 font-bold text-zinc-950">{stat.canonical_name}</td>
                      <td className="p-4 text-zinc-600 font-mono text-xs">{stat.field_type || 'unknown'}</td>
                      <td className="p-4">
                        {stat.required ? (
                          <span className="bg-rose-50 border border-rose-250 text-rose-700 px-2 py-0.5 rounded text-[10px] font-black uppercase">Required</span>
                        ) : (
                          <span className="bg-zinc-100 border border-zinc-200 text-zinc-500 px-2 py-0.5 rounded text-[10px] font-black uppercase">Optional</span>
                        )}
                      </td>
                      <td className="p-4">
                        <span className="bg-blue-50 border border-blue-200 text-blue-800 px-2 py-0.5 rounded text-xs font-bold font-mono">
                          {stat.ats_type || 'generic'}
                        </span>
                      </td>
                      <td className="p-4 text-zinc-650 font-semibold">{stat.company || 'All Companies'}</td>
                      <td className="p-4 text-right font-black text-zinc-950 text-base">{stat.total_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="py-10 text-center border-2 border-dashed border-zinc-300 rounded-2xl text-zinc-500 font-bold">
            No field extraction metrics captured yet. Statistics will appear once automated job application extractions are completed.
          </div>
        )}
      </div>
    </div>
  );
}

