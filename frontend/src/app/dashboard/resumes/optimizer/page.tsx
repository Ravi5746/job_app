'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/services/api';
import { 
  Sparkles, 
  FileText, 
  CheckCircle, 
  RefreshCw, 
  ArrowLeft,
  Search,
  TrendingUp
} from 'lucide-react';

interface Resume {
  id: number;
  name: string;
  content: string;
}

export default function ResumeOptimizerPage() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [targetRole, setTargetRole] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [isLoadingResumes, setIsLoadingResumes] = useState(true);
  
  // Optimization result states
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizedText, setOptimizedText] = useState('');
  const [atsTips, setAtsTips] = useState<string[]>([]);
  const [optimizedSkills, setOptimizedSkills] = useState<string[]>([]);
  
  // Save states
  const [newResumeName, setNewResumeName] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchResumes();
  }, []);

  const fetchResumes = async () => {
    try {
      setIsLoadingResumes(true);
      const response = await api.get('/resumes/');
      setResumes(response.data);
      if (response.data.length > 0) {
        setSelectedResumeId(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch resumes:', error);
    } finally {
      setIsLoadingResumes(false);
    }
  };

  const handleOptimize = async () => {
    if (!selectedResumeId) {
      alert('Please select a base resume first.');
      return;
    }
    if (!targetRole.trim()) {
      alert('Please specify a target role.');
      return;
    }

    try {
      setOptimizedText('');
      setAtsTips([]);
      setOptimizedSkills([]);
      setIsOptimizing(true);

      const response = await api.post('/resumes/optimize-preview', {
        resume_id: selectedResumeId,
        target_role: targetRole,
        job_description: jobDescription
      });

      if (response.data.error) {
        alert(response.data.error);
        return;
      }

      setOptimizedText(response.data.full_resume_text || '');
      setAtsTips(response.data.ats_tips || []);
      setOptimizedSkills(response.data.optimized_skills || []);
      
      const baseResume = resumes.find(r => r.id === selectedResumeId);
      const baseNameClean = baseResume ? baseResume.name.replace(/\.[^/.]+$/, "") : "Resume";
      setNewResumeName(`${targetRole.replace(/\s+/g, '_')}_${baseNameClean}`);

    } catch (error) {
      console.error('Optimization failed:', error);
      alert('Failed to optimize resume. Please verify your OpenRouter key.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleSave = async () => {
    if (!optimizedText.trim()) {
      alert('No optimized text to save.');
      return;
    }
    if (!newResumeName.trim()) {
      alert('Please provide a name for the new resume.');
      return;
    }

    try {
      setIsSaving(true);
      
      let finalName = newResumeName.trim();
      if (!finalName.toLowerCase().endsWith('.pdf')) {
        finalName += '.pdf';
      }

      await api.post('/resumes/save-text', {
        name: finalName,
        content: optimizedText
      });

      alert('Optimized resume saved successfully! Automatic recommended job search has been queued in the background.');
      router.push('/dashboard/resumes');
    } catch (error) {
      console.error('Failed to save optimized resume:', error);
      alert('Failed to save resume.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-8 min-h-screen bg-zinc-50">
      {/* Header */}
      <div className="flex items-center space-x-4 mb-8">
        <button 
          onClick={() => router.push('/dashboard/resumes')}
          className="p-3 bg-white border-2 border-zinc-950 rounded-xl hover:bg-zinc-50 transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
        >
          <ArrowLeft size={18} className="text-zinc-900" />
        </button>
        <div>
          <h1 className="text-4xl font-black text-zinc-950 tracking-tight flex items-center space-x-3 uppercase">
            <Sparkles className="text-zinc-950" size={32} />
            <span>Resume Optimizer</span>
          </h1>
          <p className="text-zinc-600 font-bold">Optimize structure & keywords for a specific target role without data loss</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Configuration Panel */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white border-2 border-zinc-950 p-6 rounded-[2rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-6">
            <h3 className="text-lg font-black text-zinc-950 uppercase border-b-2 border-zinc-950 pb-3">1. Configuration</h3>

            {/* Select Resume */}
            <div className="space-y-2">
              <label className="text-xs font-black uppercase text-zinc-500 tracking-wider">Select Base Resume</label>
              {isLoadingResumes ? (
                <div className="py-2 text-zinc-500 font-bold flex items-center space-x-2">
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Loading resumes...</span>
                </div>
              ) : resumes.length === 0 ? (
                <div className="p-4 bg-rose-50 border-2 border-rose-950 rounded-xl text-rose-700 text-sm font-bold">
                  No resumes found. Please upload a base resume in the Resumes page first.
                </div>
              ) : (
                <div className="relative">
                  <select
                    value={selectedResumeId || ''}
                    onChange={(e) => setSelectedResumeId(Number(e.target.value))}
                    className="w-full bg-white border-2 border-zinc-950 rounded-xl px-4 py-3 text-sm font-bold text-zinc-900 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] focus:outline-none cursor-pointer appearance-none pr-10"
                  >
                    {resumes.map((res) => (
                      <option key={res.id} value={res.id}>
                        {res.name}
                      </option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-zinc-950">
                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                      <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                    </svg>
                  </div>
                </div>
              )}
            </div>

            {/* Target Role Input */}
            <div className="space-y-2">
              <label className="text-xs font-black uppercase text-zinc-500 tracking-wider">Target Job / Field</label>
              <input
                type="text"
                placeholder="e.g. AI Engineer, Python Developer"
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                className="w-full bg-white border-2 border-zinc-950 rounded-xl py-3 px-4 text-zinc-900 placeholder:text-zinc-400 outline-none focus:ring-0 focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
              />
            </div>

            {/* Job Description Textarea */}
            <div className="space-y-2">
              <label className="text-xs font-black uppercase text-zinc-500 tracking-wider">Target Job Description (Optional)</label>
              <textarea
                placeholder="Paste the target job description or requirements here to tailor specifically for it..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                className="w-full h-32 bg-white border-2 border-zinc-950 rounded-xl py-3 px-4 text-zinc-900 placeholder:text-zinc-400 outline-none focus:ring-0 focus:border-zinc-950 transition-all font-semibold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] resize-none text-sm"
              />
            </div>

            {/* Submit Button */}
            <button
              onClick={handleOptimize}
              disabled={isOptimizing || resumes.length === 0}
              className="w-full bg-zinc-900 hover:bg-zinc-800 text-white font-black py-4 rounded-2xl transition-all flex items-center justify-center space-x-2 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] disabled:opacity-50 cursor-pointer"
            >
              {isOptimizing ? (
                <>
                  <RefreshCw className="animate-spin" size={18} />
                  <span>Optimizing keywords...</span>
                </>
              ) : (
                <>
                  <Sparkles size={18} />
                  <span>Optimize Resume</span>
                </>
              )}
            </button>
          </div>

          {/* ATS Tips Panel */}
          {atsTips.length > 0 && (
            <div className="bg-white border-2 border-zinc-950 p-6 rounded-[2rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-6">
              <h3 className="text-lg font-black text-zinc-950 uppercase border-b-2 border-zinc-950 pb-3 flex items-center space-x-2">
                <TrendingUp size={20} />
                <span>ATS Strategy Tips</span>
              </h3>
              <div className="space-y-4">
                {atsTips.map((tip, idx) => (
                  <div key={idx} className="flex items-start space-x-3 p-3 bg-zinc-50 border border-zinc-200 rounded-xl">
                    <div className="w-5 h-5 rounded-full bg-zinc-900 flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-[10px] font-black text-white">{idx + 1}</span>
                    </div>
                    <p className="text-xs text-zinc-700 font-bold leading-relaxed">{tip}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Editor & Preview Panel */}
        <div className="lg:col-span-2 space-y-6">
          {optimizedText ? (
            <div className="bg-white border-2 border-zinc-950 p-6 rounded-[2rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-6 flex flex-col min-h-[70vh]">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-zinc-950 pb-3">
                <h3 className="text-lg font-black text-zinc-950 uppercase flex items-center space-x-2">
                  <FileText size={20} />
                  <span>Interactive Editor</span>
                </h3>
                <span className="text-xs font-black uppercase bg-emerald-100 text-emerald-800 border border-emerald-250 py-1 px-3 rounded-full">
                  Page density & layout preserved
                </span>
              </div>

              {/* Keywords Added */}
              {optimizedSkills.length > 0 && (
                <div className="flex flex-wrap gap-2 items-center bg-zinc-50 border border-zinc-200 p-3 rounded-xl">
                  <span className="text-xs font-black text-zinc-500 uppercase tracking-wider mr-1">Optimized Skills:</span>
                  {optimizedSkills.map((skill, idx) => (
                    <span key={idx} className="text-[10px] font-black uppercase bg-purple-50 text-purple-700 border border-purple-200 py-0.5 px-2 rounded-lg">
                      {skill}
                    </span>
                  ))}
                </div>
              )}

              {/* Editable Text Area */}
              <div className="flex-1 flex flex-col">
                <label className="text-[10px] uppercase font-black tracking-wider text-zinc-500 mb-2">Editable Plain Text Resume Content</label>
                <textarea
                  value={optimizedText}
                  onChange={(e) => setOptimizedText(e.target.value)}
                  className="w-full flex-1 min-h-[50vh] bg-zinc-50 border-2 border-zinc-950 p-6 rounded-2xl text-zinc-800 font-mono text-sm leading-relaxed outline-none focus:border-zinc-950 resize-y shadow-inner"
                  placeholder="AI optimized text will appear here..."
                />
              </div>

              {/* Save Section */}
              <div className="border-t-2 border-zinc-950 pt-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div className="flex-1 space-y-2">
                  <label className="text-xs font-black uppercase text-zinc-500 tracking-wider">Optimized Resume Name</label>
                  <input
                    type="text"
                    placeholder="e.g. AI_Engineer_Resume"
                    value={newResumeName}
                    onChange={(e) => setNewResumeName(e.target.value)}
                    className="w-full bg-white border-2 border-zinc-950 rounded-xl py-3 px-4 text-zinc-900 placeholder:text-zinc-400 outline-none focus:ring-0 focus:border-zinc-950 font-bold shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                  />
                </div>
                <button
                  onClick={handleSave}
                  disabled={isSaving || !optimizedText.trim() || !newResumeName.trim()}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-black py-4 px-8 rounded-2xl transition-all flex items-center justify-center space-x-2 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer whitespace-nowrap disabled:opacity-50"
                >
                  {isSaving ? (
                    <>
                      <RefreshCw className="animate-spin" size={18} />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle size={18} />
                      <span>Save and Trigger Recommendations</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-white border-2 border-zinc-950 rounded-[2rem] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] h-full flex flex-col items-center justify-center text-center p-12 py-24 min-h-[60vh]">
              <div className="w-20 h-20 bg-zinc-100 rounded-2xl flex items-center justify-center mb-6 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                <Search size={36} className="text-zinc-950" />
              </div>
              <h3 className="text-2xl font-black text-zinc-950 mb-2 uppercase">No Optimization Active</h3>
              <p className="text-zinc-600 max-w-md font-bold mb-8">
                Select your base resume, enter the target role (e.g., Python Developer) on the left, and click optimize to generate a professionally tailored text resume draft.
              </p>
              <div className="flex flex-wrap gap-4 justify-center">
                <span className="bg-zinc-100 border border-zinc-300 text-zinc-700 text-xs font-black px-4 py-2 rounded-xl">
                  • 2-Page Density Kept
                </span>
                <span className="bg-zinc-100 border border-zinc-300 text-zinc-700 text-xs font-black px-4 py-2 rounded-xl">
                  • Zero Section Deletions
                </span>
                <span className="bg-zinc-100 border border-zinc-300 text-zinc-700 text-xs font-black px-4 py-2 rounded-xl">
                  • Keyword Optimization
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
