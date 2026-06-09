'use client';

import { useState, useEffect, Suspense } from 'react';
import api from '@/services/api';
import {
  Briefcase,
  Search,
  Filter,
  MapPin,
  ExternalLink,
  Globe,
  SearchIcon,
  Eye,
  X,
  Building2,
  Calendar,
  Share2,
  FileText,
  ChevronRight,
  ChevronLeft,
  LayoutGrid,
  Layers,
  RefreshCw,
  Database,
  CheckCircle,
  Trash2,
  Zap,
  Bookmark,
  BookmarkCheck
} from 'lucide-react';

interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  url: string;
  source: string;
  status: string;
  category: string;
  skills?: string;
  requirements?: string;
  match_score?: number;
  match_suggestions?: string;
  tailored_resume?: string;
  created_at: string;
}

export default function SavedJobsPage() {
  return (
    <Suspense fallback={<div>Loading Saved Jobs...</div>}>
      <SavedJobsContent />
    </Suspense>
  );
}

function SavedJobsContent() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [applyingJobId, setApplyingJobId] = useState<number | null>(null);

  useEffect(() => {
    fetchSavedJobs();
  }, []);

  const fetchSavedJobs = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/jobs/saved-jobs');
      setJobs(response.data);
    } catch (error) {
      console.error('Failed to fetch saved jobs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUnsaveJob = async (jobId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await api.delete(`/jobs/${jobId}/save`);
      setJobs(prev => prev.filter(j => j.id !== jobId));
      if (selectedJob?.id === jobId) setSelectedJob(null);
    } catch (error) {
      console.error('Failed to unsave job:', error);
    }
  };

  const handleApplyExternally = async (job: Job) => {
    if (!job.url) return;
    window.open(job.url, '_blank', 'noopener,noreferrer');
  };

  const handleAutoApply = async (jobId: number) => {
    try {
      setApplyingJobId(jobId);
      setIsApplying(true);
      const response = await api.post(`/jobs/apply/${jobId}`);
      const data = response.data;
      
      if (data.status === 'queued' && data.task_id) {
        const taskId = data.task_id;
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await api.get(`/jobs/apply/status/${taskId}`);
            const statusData = statusRes.data;
            const state = statusData.status;
            
            if (['SUCCESS', 'COMPLETED', 'WARNING', 'FAILURE', 'FAILED'].includes(state)) {
              clearInterval(pollInterval);
              setApplyingJobId(null);
              setIsApplying(false);
              
              const result = statusData.result || {};
              if (state === 'SUCCESS' || state === 'COMPLETED') {
                alert(`🎉 Success: ${result.message || 'Application submitted and verified!'}`);
                if (selectedJob && selectedJob.id === jobId) {
                  setSelectedJob(prev => prev ? { ...prev, status: 'applied' } : null);
                }
              } else if (state === 'WARNING') {
                alert(`⚠️ Warning: ${result.message || 'Check the application status manually.'}`);
              } else {
                alert(`❌ Failed: ${result.message || 'Automation failed.'}`);
              }
              fetchSavedJobs();
            }
          } catch (pollErr) {
            console.error('Polling error:', pollErr);
            clearInterval(pollInterval);
            setApplyingJobId(null);
            setIsApplying(false);
            alert('Error occurred while checking application status.');
          }
        }, 2000);
      } else {
        if (data.status === 'success') {
          alert(`🎉 Success: ${data.message || 'Application submitted and verified!'}`);
          if (selectedJob && selectedJob.id === jobId) {
            setSelectedJob(prev => prev ? { ...prev, status: 'applied' } : null);
          }
        } else if (data.status === 'warning') {
          alert(`⚠️ Warning: ${data.message}\n\nPlease complete manually at the opened URL.`);
          if (data.url) {
            window.open(data.url, '_blank', 'noopener,noreferrer');
          }
        } else {
          alert(`Status: ${data.message || 'Automation run complete.'}`);
        }
        fetchSavedJobs();
        setApplyingJobId(null);
        setIsApplying(false);
      }
    } catch (error: any) {
      console.error('Auto apply failed:', error);
      alert(error.response?.data?.detail || 'Failed to auto-apply to the job.');
      setApplyingJobId(null);
      setIsApplying(false);
    }
  };

  return (
    <div className="p-8 relative min-h-screen bg-zinc-50">
      <div className="flex flex-col mb-8 gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-black text-zinc-950 tracking-tight mb-2">Saved Jobs</h1>
            <div className="flex items-center space-x-2 text-zinc-600 font-bold">
              <span>Your bookmarked opportunities</span>
            </div>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center h-64 space-y-4">
          <div className="w-12 h-12 border-4 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-zinc-600 font-black">Loading your saved jobs...</p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6">
            {jobs.length > 0 ? (
              jobs.map((job) => (
                <div
                  key={job.id}
                  className="group relative flex flex-col md:flex-row items-start md:items-center gap-6 p-6 rounded-[2rem] bg-white border-2 border-zinc-950 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-all duration-300 hover:translate-y-[-2px]"
                >
                  <div className="w-16 h-16 shrink-0 rounded-2xl bg-zinc-100 border-2 border-zinc-950 flex items-center justify-center shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] group-hover:scale-105 transition-transform duration-300">
                    <Briefcase size={30} className="text-zinc-900" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <h3 className="text-xl font-black text-zinc-950 group-hover:text-zinc-800 transition-colors truncate">{job.title}</h3>
                      {job.match_score && (
                        <span className="bg-emerald-100 text-emerald-800 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider border border-emerald-250">ATS Score: {job.match_score}%</span>
                      )}
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider border ${
                        job.status === 'applied' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                        job.status === 'interviewing' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                        job.status === 'closed' ? 'bg-zinc-200 text-zinc-700 border-zinc-300' :
                        job.status === 'rejected' ? 'bg-rose-100 text-rose-800 border-rose-250' :
                        'bg-emerald-100 text-emerald-800 border-emerald-250'
                      }`}>
                        {job.status || 'active'}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-y-2 gap-x-4 text-sm text-zinc-600">
                      <span className="flex items-center space-x-1.5 font-bold text-zinc-800">
                        <Building2 size={14} className="text-zinc-600" />
                        <span className="truncate max-w-[150px]">{job.company}</span>
                      </span>
                      <span className="flex items-center space-x-1.5 font-semibold">
                        <MapPin size={14} className="text-zinc-500" />
                        <span>{job.location}</span>
                      </span>
                      <span className="flex items-center space-x-1.5">
                        <Globe size={14} className="text-zinc-500" />
                        <span className="bg-zinc-100 border-2 border-zinc-950 px-2.5 py-0.5 rounded-lg text-[10px] text-zinc-900 font-extrabold uppercase tracking-wider">{job.source}</span>
                      </span>
                      <span className="flex items-center space-x-1.5">
                        <Layers size={14} className="text-zinc-500" />
                        <span className="text-zinc-600 font-bold bg-zinc-100 border border-zinc-200 px-2 py-0.5 rounded-lg text-xs">{job.category}</span>
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 shrink-0">
                    <button
                      onClick={(e) => handleUnsaveJob(job.id, e)}
                      className="flex items-center justify-center p-3.5 rounded-xl border-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-all cursor-pointer bg-amber-100 border-amber-900 text-amber-700 hover:bg-amber-200"
                      title="Unsave Job"
                    >
                      <BookmarkCheck size={18} className="fill-amber-700" />
                    </button>
                    <button
                      onClick={() => setSelectedJob(job)}
                      className="flex items-center space-x-2 px-5 py-3 rounded-xl bg-white hover:bg-zinc-50 text-zinc-900 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-all font-black text-sm cursor-pointer"
                      title="View Details"
                    >
                      <Eye size={18} />
                      <span>View</span>
                    </button>
                    <button
                      onClick={() => handleAutoApply(job.id)}
                      disabled={isApplying}
                      className={`flex items-center space-x-2 px-5 py-3.5 rounded-xl border-2 border-zinc-950 font-black transition-all shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] whitespace-nowrap text-sm cursor-pointer ${
                        applyingJobId === job.id
                          ? 'bg-purple-100 text-purple-700'
                          : 'bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-50'
                      }`}
                    >
                      {applyingJobId === job.id ? (
                        <>
                          <RefreshCw className="animate-spin" size={16} />
                          <span>Applying...</span>
                        </>
                      ) : (
                        <>
                          <Zap size={16} />
                          <span>Auto Apply</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleApplyExternally(job)}
                      className="flex items-center space-x-2 px-6 py-3.5 rounded-xl border-2 border-zinc-950 font-black transition-all shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] whitespace-nowrap text-sm bg-zinc-900 hover:bg-zinc-800 text-white cursor-pointer"
                    >
                      <span>Apply Now</span>
                      <ExternalLink size={16} />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-24 bg-white rounded-[2rem] border-2 border-zinc-950 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
                <div className="w-20 h-20 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-6 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                  <Bookmark size={36} className="text-amber-900" />
                </div>
                <div className="text-zinc-950 mb-2 font-black text-2xl">No saved jobs yet.</div>
                <p className="text-zinc-700 mb-8 text-base font-bold">Go to the explore page to discover and bookmark jobs.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Job Details Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-all duration-300">
          <div className="bg-[#fdfcfb] border-[3px] border-zinc-950 w-full max-w-4xl rounded-[2rem] overflow-hidden shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200">
            {/* Top Header */}
            <div className="p-8 border-b-[3px] border-zinc-950 flex items-start justify-between bg-white">
              <div className="flex items-center space-x-6">
                <div className="w-[72px] h-[72px] rounded-[1.25rem] bg-white border-[3px] border-zinc-950 flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] shrink-0">
                  <Briefcase size={32} className="text-zinc-900" />
                </div>
                <div className="flex flex-col justify-center">
                  <div className="flex items-center space-x-4 mb-2">
                    <h2 className="text-[1.75rem] font-black text-zinc-950 tracking-tight leading-none">{selectedJob.title}</h2>
                    <span className="text-[11px] font-black px-3 py-1 rounded-full uppercase tracking-wider bg-emerald-100 text-emerald-800">
                      {selectedJob.status || 'ACTIVE'}
                    </span>
                  </div>
                  <p className="text-zinc-600 font-bold text-lg">{selectedJob.company}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="p-3 bg-white border-[3px] border-zinc-950 rounded-2xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer transition-all"
              >
                <X size={24} className="text-zinc-900" />
              </button>
            </div>

            {/* Middle Section */}
            <div className="p-8 overflow-y-auto flex-1 space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Location Card */}
                <div className="bg-white p-5 rounded-[1.5rem] border-[3px] border-zinc-950 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                  <div className="text-zinc-500 text-[10px] uppercase font-black tracking-widest mb-3">Location</div>
                  <div className="flex items-center space-x-3 text-zinc-900 font-bold">
                    <MapPin size={20} className="text-zinc-900" />
                    <span className="text-base">{selectedJob.location}</span>
                  </div>
                </div>
                {/* Platform Card */}
                <div className="bg-white p-5 rounded-[1.5rem] border-[3px] border-zinc-950 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                  <div className="text-zinc-500 text-[10px] uppercase font-black tracking-widest mb-3">Platform</div>
                  <div className="flex items-center space-x-3 text-zinc-900 font-bold">
                    <Globe size={20} className="text-zinc-900" />
                    <span className="text-base uppercase tracking-widest">{selectedJob.source}</span>
                  </div>
                </div>
                {/* Category Card */}
                <div className="bg-white p-5 rounded-[1.5rem] border-[3px] border-zinc-950 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                  <div className="text-zinc-500 text-[10px] uppercase font-black tracking-widest mb-3">Category</div>
                  <div className="flex items-center space-x-3 text-zinc-900 font-bold">
                    <Layers size={20} className="text-zinc-900" />
                    <span className="text-base">{selectedJob.category}</span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-xl font-black mb-6 flex items-center space-x-3 text-zinc-900 uppercase tracking-tight">
                  <FileText size={24} className="text-zinc-900" />
                  <span>Job Description</span>
                </h4>
                <div className="text-zinc-800 leading-relaxed text-base whitespace-pre-wrap font-medium">
                  {selectedJob.description}
                </div>
              </div>

              {selectedJob.requirements && (
                <div className="mt-8">
                  <h4 className="text-xl font-black mb-6 flex items-center space-x-3 text-zinc-900 uppercase tracking-tight">
                    <CheckCircle size={24} className="text-zinc-900" />
                    <span>Requirements</span>
                  </h4>
                  <div className="text-zinc-800 leading-relaxed text-base whitespace-pre-wrap font-medium">
                    {selectedJob.requirements}
                  </div>
                </div>
              )}
              
              {selectedJob.skills && (
                <div className="mt-8">
                  <h4 className="text-xl font-black mb-6 flex items-center space-x-3 text-zinc-900 uppercase tracking-tight">
                    <Zap size={24} className="text-zinc-900" />
                    <span>Skills</span>
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedJob.skills.split(',').map((skill, i) => (
                      <span key={i} className="px-4 py-2 bg-white text-zinc-900 rounded-[1rem] border-[3px] border-zinc-950 font-black text-sm shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                        {skill.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Bottom Section */}
            <div className="p-8 border-t-[3px] border-zinc-950 bg-white">
              <div className="flex flex-col gap-5">
                <div className="flex flex-col md:flex-row items-end gap-5">
                  <div className="flex-1 w-full">
                    <label className="block text-zinc-500 text-[10px] uppercase font-black tracking-widest mb-2">Status</label>
                    <div className="relative">
                      <select className="w-full appearance-none bg-white border-[3px] border-zinc-950 rounded-[1.25rem] px-5 py-4 font-black text-zinc-900 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] outline-none focus:ring-0 cursor-pointer">
                        <option value="active">Active</option>
                        <option value="applied">Applied</option>
                        <option value="interviewing">Interviewing</option>
                        <option value="rejected">Rejected</option>
                      </select>
                      <div className="absolute inset-y-0 right-5 flex items-center pointer-events-none">
                        <svg className="w-4 h-4 text-zinc-900 font-bold" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M19 9l-7 7-7-7"></path></svg>
                      </div>
                    </div>
                  </div>
                  
                  <button className="bg-white border-[3px] border-zinc-950 text-zinc-900 font-black px-8 py-4 rounded-[1.25rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex items-center justify-center space-x-3 transition-all cursor-pointer w-full md:w-auto">
                    <Search size={20} />
                    <span>Analyze Match</span>
                  </button>

                  <button 
                    onClick={() => handleAutoApply(selectedJob.id)}
                    disabled={isApplying}
                    className="bg-[#9333ea] border-[3px] border-zinc-950 text-white font-black px-8 py-4 rounded-[1.25rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex items-center justify-center space-x-3 transition-all disabled:opacity-70 cursor-pointer w-full md:w-auto"
                  >
                    {applyingJobId === selectedJob.id ? (
                      <><RefreshCw className="animate-spin" size={20} /><span>Applying...</span></>
                    ) : (
                      <><Zap size={20} /><span>Auto Apply</span></>
                    )}
                  </button>
                </div>

                <div className="flex flex-col md:flex-row items-center gap-5">
                  <button 
                    onClick={() => handleApplyExternally(selectedJob)}
                    className="flex-1 w-full bg-zinc-900 border-[3px] border-zinc-950 text-white font-black px-8 py-4 rounded-[1.25rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex items-center justify-center space-x-3 transition-all cursor-pointer"
                  >
                    <span>Apply Externally</span>
                    <ExternalLink size={20} />
                  </button>
                  
                  <button 
                    onClick={(e) => handleUnsaveJob(selectedJob.id, e)}
                    className="bg-[#fff0f0] border-[3px] border-[#4a0404] text-[#9f1212] font-black px-8 py-4 rounded-[1.25rem] shadow-[4px_4px_0px_0px-[#4a0404]] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_0px-[#4a0404]] flex items-center justify-center space-x-3 transition-all cursor-pointer w-full md:w-auto"
                  >
                    <Trash2 size={20} />
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
