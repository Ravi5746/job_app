'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
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

const INDIAN_LOCATIONS = [
  'Mumbai, Maharashtra', 'Delhi, NCR', 'Bangalore, Karnataka', 'Hyderabad, Telangana',
  'Chennai, Tamil Nadu', 'Kolkata, West Bengal', 'Pune, Maharashtra', 'Ahmedabad, Gujarat',
  'Gurgaon, Haryana', 'Noida, Uttar Pradesh', 'Jaipur, Rajasthan', 'Lucknow, Uttar Pradesh',
  'Indore, Madhya Pradesh', 'Chandigarh', 'Kochi, Kerala', 'Bhopal, Madhya Pradesh'
];

export default function JobsPage() {
  return (
    <Suspense fallback={<div>Loading Search...</div>}>
      <JobsContent />
    </Suspense>
  );
}

function JobsContent() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [locationTerm, setLocationTerm] = useState('India');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [optimizationResult, setOptimizationResult] = useState<any>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applyingJobId, setApplyingJobId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState('All');
  const [userResumes, setUserResumes] = useState<any[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const searchParams = useSearchParams();
  const [activeCategory, setActiveCategory] = useState('All');
  const [savedJobIds, setSavedJobIds] = useState<number[]>([]);

  useEffect(() => {
    const syncQuery = searchParams.get('sync');
    const resumeIdParam = searchParams.get('resume_id');

    if (resumeIdParam) {
      setSelectedResumeId(parseInt(resumeIdParam));
    }

    if (syncQuery) {
      setSearchTerm(syncQuery);
      handleSync(syncQuery);
    }
  }, [searchParams]);
  const [categories, setCategories] = useState<string[]>(['All']);
  const [page, setPage] = useState(0);
  const JOBS_PER_PAGE = 30;


  useEffect(() => {
    fetchJobs();
    fetchSavedJobs();
  }, [activeCategory, page, statusFilter]);

  const fetchSavedJobs = async () => {
    try {
      const res = await api.get('/jobs/saved-jobs');
      setSavedJobIds(res.data.map((j: Job) => j.id));
    } catch (err) {
      console.error("Failed to fetch saved jobs:", err);
    }
  };

  const fetchJobs = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/jobs/', {
        params: {
          skip: page * JOBS_PER_PAGE,
          limit: JOBS_PER_PAGE,
          category: activeCategory === 'All' ? null : activeCategory,
          status: statusFilter === 'All' ? null : statusFilter
        }
      });
      setJobs(response.data);

      // Update categories list ONLY from DB
      const allJobsResponse = await api.get('/jobs/', { params: { limit: 1000 } });
      const dbCategories = Array.from(new Set(allJobsResponse.data.map((j: Job) => j.category).filter(Boolean))) as string[];
      setCategories(['All', ...dbCategories]);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchTerm) {
      fetchJobs();
      return;
    }

    try {
      setIsLoading(true);
      // 1. Search DB first
      const dbResponse = await api.get('/jobs/db-search/', {
        params: {
          query: searchTerm,
          location: locationTerm,
          status: statusFilter === 'All' ? null : statusFilter
        }
      });

      // Use exact search term as category
      const matchedCategory = searchTerm;

      if (dbResponse.data.length > 0) {
        setJobs(dbResponse.data);
        setActiveCategory(matchedCategory);
        setPage(0);
      } else {
        // 2. If not in DB, trigger a Sync automatically
        handleSync(matchedCategory);
      }
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setIsLoading(false);
    }
  };


  const handleSync = async (targetCategory?: string) => {
    const query = targetCategory || searchTerm || activeCategory;
    if (!query || query === 'All') {
      alert('Please enter a search query (e.g. "React Developer") in the search box first to sync fresh jobs from the web.');
      return;
    }

    try {
      setIsSyncing(true);
      const response = await api.get('/jobs/search/', {
        params: {
          query: query,
          location: locationTerm
        }
      });
      setJobs(response.data);

      // Update categories list to include the new one if missing
      if (!categories.includes(query)) {
        setCategories([...categories, query]);
      }

      setActiveCategory(query);
      setPage(0);
    } catch (error) {
      console.error('Sync failed:', error);
    } finally {
      setIsSyncing(false);
    }
  };


  const handleLocationChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setLocationTerm(value);
    if (value.length > 1) {
      const filtered = INDIAN_LOCATIONS.filter(loc =>
        loc.toLowerCase().includes(value.toLowerCase())
      );
      setSuggestions(filtered);
      setShowSuggestions(true);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleOptimize = async (jobId: number) => {
    try {
      setIsOptimizing(true);
      const response = await api.post(`/jobs/optimize-resume/${jobId}`, null, {
        params: { resume_id: selectedResumeId }
      });
      setOptimizationResult(response.data);
      
      // Update local state so the score persists and shows immediately in the list
      setJobs(prev => prev.map(j => {
        if (j.id === jobId) {
          // Calculate score if possible, or just update based on response
          return { 
            ...j, 
            match_score: response.data.match_score || j.match_score,
            tailored_resume: JSON.stringify(response.data)
          };
        }
        return j;
      }));

    } catch (error) {
      console.error('Optimization failed:', error);
      alert('Failed to optimize resume. Please ensure you have uploaded a resume.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const fetchUserResumes = async () => {
    try {
      const response = await api.get('/resumes/');
      setUserResumes(response.data);
      if (response.data.length > 0 && !selectedResumeId) {
        setSelectedResumeId(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch resumes:', error);
    }
  };

  const handleUpdateStatus = async (jobId: number, newStatus: string) => {
    try {
      await api.patch(`/jobs/${jobId}`, { status: newStatus });
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: newStatus } : j));
      if (selectedJob && selectedJob.id === jobId) {
        setSelectedJob(prev => prev ? { ...prev, status: newStatus } : null);
      }
    } catch (error) {
      console.error('Failed to update job status:', error);
      alert('Failed to update job status.');
    }
  };

  const handleToggleSaveJob = async (jobId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const isSaved = savedJobIds.includes(jobId);
    try {
      if (isSaved) {
        await api.delete(`/jobs/${jobId}/save`);
        setSavedJobIds(prev => prev.filter(id => id !== jobId));
      } else {
        await api.post(`/jobs/${jobId}/save`);
        setSavedJobIds(prev => [...prev, jobId]);
      }
    } catch (error) {
      console.error('Failed to toggle save job:', error);
    }
  };

  const handleApplyExternally = async (job: Job) => {
    if (!job.url) return;
    window.open(job.url, '_blank', 'noopener,noreferrer');
    if (job.status !== 'applied') {
      await handleUpdateStatus(job.id, 'applied');
    }
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
              fetchJobs();
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
        fetchJobs();
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


  const handleDeleteJob = async (jobId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!confirm('Are you sure you want to delete this job? This action cannot be undone.')) return;

    try {
      await api.delete(`/jobs/${jobId}`);
      setJobs(prev => prev.filter(j => j.id !== jobId));
      if (selectedJob && selectedJob.id === jobId) {
        setSelectedJob(null);
        setOptimizationResult(null);
      }
    } catch (error) {
      console.error('Failed to delete job:', error);
      alert('Failed to delete the job.');
    }
  };

  const handleClearAllJobs = async () => {
    if (!confirm('Are you sure you want to delete ALL jobs from the database? This action cannot be undone.')) return;

    try {
      await api.delete('/jobs/clear-all');
      setJobs([]);
      setSelectedJob(null);
      setOptimizationResult(null);
    } catch (error) {
      console.error('Failed to clear all jobs:', error);
      alert('Failed to delete all jobs.');
    }
  };

  return (
    <div className="p-8 relative min-h-screen bg-zinc-50">
      <div className="flex flex-col mb-8 gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-black text-zinc-950 tracking-tight mb-2">Explore Jobs</h1>
            <div className="flex items-center space-x-2 text-zinc-600 font-bold">
              <span>Find indexed jobs or sync fresh ones from the web</span>
              {selectedResumeId && userResumes.find(r => r.id === selectedResumeId) && (
                <div className="flex items-center space-x-2 px-3 py-1 bg-blue-50 border border-blue-200 rounded-full text-blue-700 text-xs font-bold animate-in fade-in zoom-in duration-300">
                  <CheckCircle size={12} />
                  <span>Linked to: {userResumes.find(r => r.id === selectedResumeId)?.name}</span>
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {jobs.length > 0 && (
              <button
                onClick={handleClearAllJobs}
                className="flex items-center space-x-2 px-6 py-3 rounded-2xl bg-rose-50 border-2 border-rose-950 text-rose-700 hover:bg-rose-100 transition-all font-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
              >
                <Trash2 size={18} />
                <span>Delete All Jobs</span>
              </button>
            )}
            <button
              onClick={() => handleSync()}
              disabled={isSyncing}
              className="flex items-center space-x-2 px-6 py-3 rounded-2xl bg-white border-2 border-zinc-950 text-zinc-900 hover:bg-zinc-50 transition-all font-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw size={18} className={isSyncing ? 'animate-spin' : ''} />
              <span>{isSyncing ? 'Syncing...' : 'Sync Fresh Jobs'}</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative md:col-span-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
            <input
              type="text"
              placeholder="Search indexed jobs (e.g. Mern)"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-white border-2 border-zinc-950 rounded-2xl py-4 pl-12 pr-4 outline-none focus:ring-0 focus:border-zinc-950 transition-all text-zinc-900 placeholder:text-zinc-400 font-semibold shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]"
            />
          </div>

          <div className="relative md:col-span-1">
            <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
            <input
              type="text"
              placeholder="Location"
              value={locationTerm}
              onChange={handleLocationChange}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              className="w-full bg-white border-2 border-zinc-950 rounded-2xl py-4 pl-12 pr-4 outline-none focus:ring-0 focus:border-zinc-950 transition-all text-zinc-900 placeholder:text-zinc-400 font-semibold shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-white border-2 border-zinc-950 rounded-2xl overflow-hidden z-50 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                {suggestions.map((loc, i) => (
                  <button
                    key={i}
                    onClick={() => setLocationTerm(loc)}
                    className="w-full text-left px-4 py-3 hover:bg-zinc-50 text-sm text-zinc-900 font-bold transition-colors flex items-center space-x-2 border-b border-zinc-150 last:border-0"
                  >
                    <MapPin size={14} className="text-zinc-500" />
                    <span>{loc}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={handleSearch}
            className="bg-zinc-900 hover:bg-zinc-800 text-white font-black py-4 px-8 rounded-2xl transition-all flex items-center justify-center space-x-3 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
          >
            <Database size={20} />
            <span>Search Database</span>
          </button>
        </div>

        {/* Categories Tabs & Status Filter */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4 overflow-x-auto pb-2 scrollbar-hide">
            <div className="flex items-center bg-white p-1.5 rounded-2xl border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => { setActiveCategory(cat); setPage(0); setSearchTerm(''); }}
                  className={`px-6 py-2.5 rounded-xl text-sm font-bold transition-all whitespace-nowrap cursor-pointer ${activeCategory === cat
                      ? 'bg-zinc-900 text-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]'
                      : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
                    }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            <span className="font-extrabold text-zinc-950 text-sm uppercase tracking-wider flex items-center space-x-1.5">
              <Filter size={16} className="text-zinc-950" />
              <span>Status:</span>
            </span>
            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
                className="bg-white border-2 border-zinc-950 rounded-xl px-4 py-2.5 text-sm font-black text-zinc-900 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] focus:outline-none cursor-pointer appearance-none pr-10"
              >
                <option value="All">All Statuses</option>
                <option value="active">Active</option>
                <option value="applied">Applied</option>
                <option value="interviewing">Interviewing</option>
                <option value="closed">Closed</option>
                <option value="rejected">Rejected</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-zinc-950">
                <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                  <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      {isLoading || isSyncing ? (
        <div className="flex flex-col items-center justify-center h-64 space-y-4">
          <div className="w-12 h-12 border-4 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-zinc-600 font-black">{isSyncing ? 'Scraping fresh jobs...' : 'Loading indexed jobs...'}</p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6">
            {jobs.length > 0 ? (
              jobs.map((job, idx) => (
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
                      onClick={(e) => handleToggleSaveJob(job.id, e)}
                      className={`flex items-center justify-center p-3.5 rounded-xl border-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-all cursor-pointer ${
                        savedJobIds.includes(job.id) 
                          ? 'bg-amber-100 border-amber-900 text-amber-700 hover:bg-amber-200' 
                          : 'bg-white border-zinc-950 text-zinc-600 hover:bg-zinc-50'
                      }`}
                      title={savedJobIds.includes(job.id) ? "Unsave Job" : "Save Job"}
                    >
                      {savedJobIds.includes(job.id) ? <BookmarkCheck size={18} className="fill-amber-700" /> : <Bookmark size={18} />}
                    </button>
                    <button
                      onClick={(e) => handleDeleteJob(job.id, e)}
                      className="flex items-center justify-center p-3.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border-2 border-rose-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-all cursor-pointer"
                      title="Delete Job"
                    >
                      <Trash2 size={18} />
                    </button>
                    <button
                      onClick={() => {
                        setSelectedJob(job);
                        fetchUserResumes();
                        if (job.tailored_resume) {
                          try {
                            setOptimizationResult(JSON.parse(job.tailored_resume));
                          } catch (e) {
                            console.error('Failed to parse tailored resume:', e);
                          }
                        }
                      }}
                      className="flex items-center space-x-2 px-5 py-3 rounded-xl bg-white hover:bg-zinc-50 text-zinc-900 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transition-all font-black text-sm cursor-pointer"
                      title="View Details & Tailored Resume"
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
                <div className="w-20 h-20 bg-zinc-100 rounded-2xl flex items-center justify-center mx-auto mb-6 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                  <Search size={36} className="text-zinc-950" />
                </div>
                <div className="text-zinc-950 mb-2 font-black text-2xl">No jobs found in Database.</div>
                <p className="text-zinc-700 mb-8 text-base font-bold">Would you like to sync fresh jobs from the web?</p>
                <button
                  onClick={() => handleSync()}
                  className="bg-zinc-900 hover:bg-zinc-800 text-white font-black py-4 px-8 rounded-2xl transition-all flex items-center justify-center space-x-3 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer mx-auto"
                >
                  <RefreshCw size={18} />
                  <span>Sync Fresh Jobs Now</span>
                </button>
              </div>
            )}
          </div>

          {/* Pagination */}
          {jobs.length > 0 && (
            <div className="flex items-center justify-between mt-12 pt-8 border-t-2 border-zinc-950">
              <p className="text-sm text-zinc-600 font-bold">
                Showing <span className="text-zinc-950 font-black">{page * JOBS_PER_PAGE + 1}</span> to <span className="text-zinc-950 font-black">{Math.min((page + 1) * JOBS_PER_PAGE, jobs.length + page * JOBS_PER_PAGE)}</span> jobs
              </p>
              <div className="flex items-center space-x-3">
                <button
                  disabled={page === 0}
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  className="p-3 rounded-xl bg-white border-2 border-zinc-950 hover:bg-zinc-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] cursor-pointer"
                >
                  <ChevronLeft size={20} />
                </button>
                <div className="bg-zinc-900 border-2 border-zinc-950 px-4 py-2 rounded-xl text-sm font-black text-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  Page {page + 1}
                </div>
                <button
                  disabled={jobs.length < JOBS_PER_PAGE}
                  onClick={() => setPage(p => p + 1)}
                  className="p-3 rounded-xl bg-white border-2 border-zinc-950 hover:bg-zinc-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] cursor-pointer"
                >
                  <ChevronRight size={20} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Job Details Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-all duration-300">
          <div className="bg-white border-4 border-zinc-950 w-full max-w-3xl rounded-[2rem] overflow-hidden shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200">
            <div className="p-8 border-b-2 border-zinc-950 flex items-center justify-between bg-zinc-50">
              <div className="flex items-center space-x-6">
                <div className="w-16 h-16 rounded-2xl bg-zinc-100 border-2 border-zinc-950 flex items-center justify-center shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <Briefcase size={32} className="text-zinc-900" />
                </div>
                <div>
                  <div className="flex items-center space-x-3 mb-1">
                    <h2 className="text-2xl font-black text-zinc-950 tracking-tight">{selectedJob.title}</h2>
                    {selectedJob.match_score && (
                      <span className="flex items-center space-x-1.5 px-3 py-1 bg-emerald-100 text-emerald-800 text-[11px] font-black rounded-full border border-emerald-250 uppercase tracking-wider">
                        <CheckCircle size={12} />
                        <span>ATS Match: {selectedJob.match_score}%</span>
                      </span>
                    )}
                    <span className={`text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider border ${
                      selectedJob.status === 'applied' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                      selectedJob.status === 'interviewing' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                      selectedJob.status === 'closed' ? 'bg-zinc-200 text-zinc-700 border-zinc-300' :
                      selectedJob.status === 'rejected' ? 'bg-rose-100 text-rose-800 border-rose-250' :
                      'bg-emerald-100 text-emerald-800 border-emerald-250'
                    }`}>
                      {selectedJob.status || 'active'}
                    </span>
                  </div>
                  <p className="text-zinc-600 font-bold">{selectedJob.company}</p>
                </div>
              </div>
              <button
                onClick={() => { setSelectedJob(null); setOptimizationResult(null); }}
                className="p-2.5 bg-white hover:bg-zinc-50 border-2 border-zinc-950 rounded-xl transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] cursor-pointer"
              >
                <X size={20} className="text-zinc-900" />
              </button>
            </div>

            <div className="p-8 overflow-y-auto flex-1 space-y-8 bg-zinc-50">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white p-5 rounded-2xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <div className="text-zinc-500 text-[10px] uppercase font-black tracking-wider mb-2">Location</div>
                  <div className="flex items-center space-x-2 text-zinc-900 font-black">
                    <MapPin size={18} className="text-zinc-900" />
                    <span className="text-sm">{selectedJob.location}</span>
                  </div>
                </div>
                <div className="bg-white p-5 rounded-2xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <div className="text-zinc-500 text-[10px] uppercase font-black tracking-wider mb-2">Platform</div>
                  <div className="flex items-center space-x-2 text-zinc-900 font-black">
                    <Globe size={18} className="text-zinc-900" />
                    <span className="text-sm uppercase tracking-wider">{selectedJob.source}</span>
                  </div>
                </div>
                <div className="bg-white p-5 rounded-2xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <div className="text-zinc-500 text-[10px] uppercase font-black tracking-wider mb-2">Category</div>
                  <div className="flex items-center space-x-2 text-zinc-900 font-black">
                    <Layers size={18} className="text-zinc-900" />
                    <span className="text-sm">{selectedJob.category}</span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-lg font-black mb-4 flex items-center space-x-2 text-zinc-900 uppercase">
                  <FileText size={20} className="text-zinc-900" />
                  <span>Job Description</span>
                </h4>
                <div className="text-zinc-800 leading-relaxed text-sm whitespace-pre-wrap bg-white p-8 rounded-2xl border-2 border-zinc-950 font-medium shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                  {selectedJob.description}
                </div>
              </div>

              {/* Resume Selection */}
              {!optimizationResult && userResumes.length > 0 && (
                <div className="bg-white border-2 border-zinc-950 rounded-2xl p-8 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                  <h4 className="text-lg font-black mb-4 text-zinc-900 flex items-center space-x-2 uppercase">
                    <FileText size={20} className="text-zinc-900" />
                    <span>Select Resume for this Job</span>
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {userResumes.map((res) => (
                      <button
                        key={res.id}
                        onClick={() => setSelectedResumeId(res.id)}
                        className={`p-4 rounded-xl border-2 transition-all text-left flex items-center justify-between group cursor-pointer ${selectedResumeId === res.id
                            ? 'border-zinc-950 bg-blue-50 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]'
                            : 'border-zinc-300 hover:border-zinc-950 bg-zinc-50'
                          }`}
                      >
                        <div className="flex items-center space-x-3">
                          <FileText size={18} className={selectedResumeId === res.id ? 'text-zinc-900' : 'text-zinc-500'} />
                          <span className={`text-sm font-bold truncate max-w-[120px] ${selectedResumeId === res.id ? 'text-zinc-900 font-black' : 'text-zinc-600'}`}>
                            {res.name}
                          </span>
                        </div>
                        {selectedResumeId === res.id && <CheckCircle size={16} className="text-zinc-900" />}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {selectedJob.skills && (
                <div>
                  <h4 className="text-lg font-black mb-4 flex items-center space-x-2 text-zinc-900 uppercase">
                    <RefreshCw size={20} className="text-zinc-900" />
                    <span>Technical Skills</span>
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedJob.skills.split(',').map((skill, i) => (
                      <span key={i} className="px-4 py-2 bg-purple-50 text-purple-700 rounded-xl border border-purple-200 font-extrabold text-xs">
                        {skill.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedJob.requirements && (
                <div>
                  <h4 className="text-lg font-black mb-4 flex items-center space-x-2 text-zinc-900 uppercase">
                    <CheckCircle size={20} className="text-zinc-900" />
                    <span>Requirements</span>
                  </h4>
                  <div className="text-zinc-800 leading-relaxed text-sm whitespace-pre-wrap bg-white p-6 rounded-2xl border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                    {selectedJob.requirements}
                  </div>
                </div>
              )}

              {selectedJob.match_suggestions && !optimizationResult && (
                <div className="bg-blue-50 border-2 border-blue-200 rounded-2xl p-8 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                  <h4 className="text-lg font-black mb-4 text-blue-900 flex items-center space-x-2 uppercase">
                    <Database size={20} />
                    <span>AI Analysis & Match Score</span>
                  </h4>
                  <div className="text-blue-800 text-sm font-semibold leading-relaxed whitespace-pre-wrap">
                    {selectedJob.match_suggestions}
                  </div>
                </div>
              )}

              {optimizationResult && (
                <div className="bg-zinc-100 border-2 border-zinc-950 rounded-2xl p-8 relative overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                  <h4 className="text-xl font-black mb-8 text-zinc-950 flex items-center space-x-3 uppercase">
                    <FileText size={24} />
                    <span>Original Resume Analysis</span>
                  </h4>
                  
                  <div className="bg-white rounded-2xl border-2 border-zinc-950 shadow-lg overflow-hidden font-serif">
                    {/* Professional Header Section */}
                    <div className="p-12 pb-6 border-b border-zinc-200 bg-zinc-50">
                      <div className="flex flex-col items-start space-y-2">
                        <h2 className="text-4xl font-bold text-zinc-900 tracking-tight">
                          {optimizationResult.full_resume_text?.split('\n')[0]?.replace('#', '') || 'Sapan Kumar'}
                        </h2>
                        <div className="text-zinc-600 font-bold text-sm tracking-widest uppercase">
                          Original Content for {selectedJob.title}
                        </div>
                      </div>
                    </div>
 
                    {/* Document Body */}
                    <div className="p-12 pt-8 text-zinc-800 leading-relaxed text-[15px] max-h-[700px] overflow-y-auto scrollbar-hide">
                      <div className="space-y-8">
                        {optimizationResult.full_resume_text?.split('\n\n').map((section: string, idx: number) => {
                          const lines = section.split('\n');
                          const title = lines[0];
                          const content = lines.slice(1).join('\n');
                          const isHeader = title.length < 50 && (title === title.toUpperCase() || idx === 0);
 
                          return (
                            <div key={idx} className="group">
                              {isHeader ? (
                                <div className="mb-4">
                                  <h3 className="text-lg font-black text-zinc-900 uppercase tracking-tighter border-b-2 border-zinc-900 pb-1 mb-3">
                                    {title}
                                  </h3>
                                  <div className="whitespace-pre-wrap text-zinc-700 font-medium leading-loose">
                                    {content}
                                  </div>
                                </div>
                              ) : (
                                <div className="whitespace-pre-wrap text-zinc-700 font-medium leading-loose">
                                  {section}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
 
                  {/* ATS Tips Section */}
                  {optimizationResult.ats_tips && (
                    <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
                      {optimizationResult.ats_tips.map((tip: string, i: number) => (
                        <div key={i} className="bg-white p-4 rounded-xl border-2 border-zinc-950 flex items-start space-x-3 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                          <div className="w-6 h-6 rounded-full bg-zinc-900 flex items-center justify-center shrink-0 mt-0.5">
                            <span className="text-[10px] font-black text-white">{i+1}</span>
                          </div>
                          <p className="text-xs text-zinc-800 font-semibold">{tip}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
 
              <div className="flex items-center space-x-6 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
                <span className="flex items-center space-x-2">
                  <Calendar size={14} />
                  <span>Posted: {new Date(selectedJob.created_at).toLocaleDateString()}</span>
                </span>
                <span className="flex items-center space-x-2">
                  <Share2 size={14} />
                  <span>Ref ID: #{selectedJob.id}</span>
                </span>
              </div>
            </div>
 
            <div className="p-8 border-t-2 border-zinc-950 bg-zinc-50 flex flex-wrap items-end gap-4">
              {/* Status Selector Dropdown */}
              <div className="flex flex-col gap-2 min-w-[180px] flex-1">
                <label className="text-[10px] uppercase font-black tracking-wider text-zinc-500">Status</label>
                <div className="relative">
                  <select
                    value={selectedJob.status}
                    onChange={(e) => handleUpdateStatus(selectedJob.id, e.target.value)}
                    className="bg-white border-2 border-zinc-950 rounded-xl px-4 py-3.5 text-sm font-black text-zinc-900 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] focus:outline-none cursor-pointer appearance-none pr-10 w-full"
                  >
                    <option value="active">Active</option>
                    <option value="applied">Applied</option>
                    <option value="interviewing">Interviewing</option>
                    <option value="closed">Closed</option>
                    <option value="rejected">Rejected</option>
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-zinc-950">
                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                      <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                    </svg>
                  </div>
                </div>
              </div>

              {!optimizationResult && (
                <button
                  onClick={() => handleOptimize(selectedJob.id)}
                  disabled={isOptimizing}
                  className="py-4.5 px-6 rounded-xl bg-white hover:bg-zinc-100 text-zinc-900 border-2 border-zinc-950 font-black transition-all flex items-center justify-center space-x-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
                >
                  {isOptimizing ? (
                    <RefreshCw className="animate-spin" size={16} />
                  ) : (
                    <Search size={16} />
                  )}
                  <span>{isOptimizing ? 'Analyzing...' : 'Analyze Match'}</span>
                </button>
              )}

              <button
                onClick={() => handleAutoApply(selectedJob.id)}
                disabled={isApplying}
                className={`py-4.5 px-6 rounded-xl border-2 border-zinc-950 font-black transition-all flex items-center justify-center space-x-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer ${
                  applyingJobId === selectedJob.id
                    ? 'bg-purple-100 text-purple-700'
                    : 'bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-50'
                }`}
              >
                {applyingJobId === selectedJob.id ? (
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
                onClick={() => handleApplyExternally(selectedJob)}
                className="flex-1 py-4.5 px-6 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-white border-2 border-zinc-950 font-black transition-all flex items-center justify-center space-x-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
              >
                <span>Apply Externally</span>
                <ExternalLink size={16} />
              </button>

              <button
                onClick={() => handleDeleteJob(selectedJob.id)}
                className="py-4.5 px-6 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border-2 border-rose-950 font-black transition-all flex items-center justify-center space-x-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
                title="Delete Job"
              >
                <Trash2 size={16} />
                <span>Delete</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
