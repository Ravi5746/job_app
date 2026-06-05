'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  FileText, 
  Upload, 
  Trash2, 
  CheckCircle2, 
  AlertCircle,
  FileUp,
  Loader2,
  MoreVertical,
  Download,
  Search
} from 'lucide-react';
import api from '@/services/api';

interface Resume {
  id: number;
  name: string;
  created_at: string;
  content: string;
  file_path?: string;
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);

  const router = useRouter();

  useEffect(() => {
    fetchResumes();
    fetchSuggestions();
  }, []);

  const handleTagClick = (tag: string, resumeId: number) => {
    // Redirect to jobs page with the search query and the linked resume ID
    router.push(`/dashboard/jobs?sync=${encodeURIComponent(tag)}&resume_id=${resumeId}`);
  };

  const fetchSuggestions = async () => {
    try {
      const response = await api.get('/resumes/suggestions');
      setSuggestions(response.data);
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
    }
  };

  const fetchResumes = async () => {
    try {
      setIsLoading(true);
      const response = await api.get('/resumes/');
      setResumes(response.data);
    } catch (err) {
      console.error('Failed to fetch resumes:', err);
      setError('Failed to load resumes');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      setError('Please upload a PDF file');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setIsUploading(true);
      setError(null);
      await api.post('/resumes/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      fetchResumes();
    } catch (err: any) {
      console.error('Upload failed:', err);
      setError(err.response?.data?.detail || 'Failed to upload resume');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this resume?')) return;
    
    try {
      await api.delete(`/resumes/${id}`);
      setResumes(resumes.filter(r => r.id !== id));
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Failed to delete resume');
    }
  };

  const handleDownload = async (resume: Resume) => {
    if (!resume.file_path) {
      const printWindow = window.open('', '_blank');
      if (!printWindow) return;

      const lines = (resume.content || '').split('\n');
      const sectionHeaders = [
        'SUMMARY', 'PROFESSIONAL SUMMARY', 'EXPERIENCE', 'PROFESSIONAL EXPERIENCE', 
        'WORK HISTORY', 'TECHNICAL SKILLS', 'SKILLS', 'CORE COMPETENCIES', 
        'PROJECTS', 'KEY PROJECTS', 'PRPROJECTS', 'EDUCATION', 'CERTIFICATIONS', 
        'LANGUAGES', 'ORGANIZATIONS', 'AWARDS', 'HONORS & AWARDS'
      ];

      let formattedHtml = '';
      let isHeaderSection = true;
      let headerLinesCount = 0;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        const upperTrimmed = trimmed.toUpperCase();

        if (trimmed === '') {
          // Collapse multiple consecutive empty lines to a single small spacer
          if (i > 0 && lines[i - 1].trim() !== '') {
            formattedHtml += '<div class="empty-line"></div>';
          }
          continue;
        }

        const isHeader = sectionHeaders.includes(upperTrimmed) || 
                         (trimmed.length > 2 && trimmed.length < 35 && /^[A-Z\s&/,\-|]+$/.test(trimmed));

        if (isHeader) {
          isHeaderSection = false;
          let displayText = trimmed;
          if (upperTrimmed === 'PRPROJECTS') {
            displayText = 'PROJECTS';
          }
          formattedHtml += `<h2 class="section-header">${displayText}</h2>`;
        } else {
          if (isHeaderSection) {
            if (headerLinesCount === 0) {
              formattedHtml += `<h1 class="resume-name">${trimmed}</h1>`;
            } else {
              formattedHtml += `<div class="resume-contact-line">${trimmed}</div>`;
            }
            headerLinesCount++;
          } else {
            // Check if it matches a bullet point pattern
            const bulletMatch = trimmed.match(/^[\u2022\u25E6\u2023\u2043\u25C6\u25C9\uFFFD•*-]\s*(.*)/);
            if (bulletMatch) {
              const bulletContent = bulletMatch[1];
              formattedHtml += `<div class="resume-bullet-line"><span class="bullet-symbol">•</span><span class="bullet-text">${bulletContent}</span></div>`;
            } else {
              formattedHtml += `<div class="resume-text-line">${trimmed}</div>`;
            }
          }
        }
      }

      printWindow.document.write(`
        <html>
          <head>
            <title>${resume.name}</title>
            <style>
              body {
                font-family: Garamond, Georgia, "Times New Roman", serif;
                padding: 0;
                color: #18181b;
                line-height: 1.3;
                font-size: 10pt;
                margin: 0;
              }
              .resume-name {
                font-size: 16pt;
                font-weight: bold;
                margin: 0 0 3px 0;
                color: #000;
                text-transform: uppercase;
                letter-spacing: 0.5px;
              }
              .resume-contact-line {
                font-size: 9pt;
                margin-bottom: 1px;
                color: #4b5563;
              }
              .section-header {
                font-size: 11pt;
                font-weight: bold;
                letter-spacing: 1px;
                border-bottom: 1.5px solid #000;
                padding-bottom: 2px;
                margin-top: 12px;
                margin-bottom: 4px;
                text-transform: uppercase;
              }
              .resume-text-line {
                margin-bottom: 2px;
                font-size: 9.5pt;
                text-align: justify;
              }
              .resume-bullet-line {
                margin-bottom: 2px;
                font-size: 9.5pt;
                display: flex;
                align-items: flex-start;
                padding-left: 12px;
                text-align: justify;
              }
              .bullet-symbol {
                margin-right: 6px;
                flex-shrink: 0;
              }
              .bullet-text {
                flex: 1;
              }
              .empty-line {
                height: 4px;
              }
              @media print {
                @page {
                  size: letter;
                  margin: 0; /* Hides browser-generated about:blank, titles, date/time */
                }
                body {
                  margin: 1.2cm 1.5cm; /* Keeps a professional margin on each page */
                  padding: 0;
                }
                .section-header {
                  page-break-after: avoid;
                }
                .resume-bullet-line, .resume-text-line {
                  page-break-inside: avoid;
                }
              }
            </style>
          </head>
          <body>${formattedHtml}</body>
        </html>
      `);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 300);
    } else {
      try {
        const response = await api.get(`/resumes/${resume.id}/download`, {
          responseType: 'blob'
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', resume.name);
        document.body.appendChild(link);
        link.click();
        link.remove();
      } catch (err) {
        console.error('Failed to download resume:', err);
        alert('Failed to download PDF.');
      }
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-black text-zinc-950 tracking-tight mb-2">My Resumes</h1>
          <p className="text-zinc-600 font-bold">Manage your resumes for AI-powered job matching</p>
        </div>
        
        <label className="cursor-pointer bg-zinc-900 hover:bg-zinc-800 text-white px-6 py-3.5 border-2 border-zinc-950 rounded-xl flex items-center space-x-2 transition-all shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
          {isUploading ? (
            <Loader2 className="animate-spin" size={20} />
          ) : (
            <Upload size={20} />
          )}
          <span className="font-black text-sm">{isUploading ? 'Uploading...' : 'Upload Resume'}</span>
          <input 
            type="file" 
            className="hidden" 
            accept=".pdf" 
            onChange={handleFileUpload}
            disabled={isUploading}
          />
        </label>
      </div>

      {error && (
        <div className="mb-6 flex items-center space-x-3 bg-red-50 border-2 border-red-200 text-red-700 p-4 rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
          <AlertCircle size={20} />
          <span className="font-bold">{error}</span>
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-zinc-600">
          <Loader2 className="animate-spin mb-4" size={40} />
          <p className="font-black">Loading your resumes...</p>
        </div>
      ) : resumes.length === 0 ? (
        <div className="bg-white border-2 border-zinc-950 rounded-3xl p-20 flex flex-col items-center text-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
          <div className="w-20 h-20 bg-zinc-100 border-2 border-zinc-950 rounded-2xl flex items-center justify-center mb-6 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
            <FileUp size={40} className="text-zinc-900" />
          </div>
          <h3 className="text-2xl font-black text-zinc-950 mb-2 uppercase tracking-tight">No resumes found</h3>
          <p className="text-zinc-600 font-semibold max-w-sm mb-8">
            Upload your resume in PDF format to start applying for jobs with AI.
          </p>
          <label className="cursor-pointer text-blue-600 hover:text-blue-800 font-extrabold transition-colors">
            Click to upload your first resume
            <input type="file" className="hidden" accept=".pdf" onChange={handleFileUpload} />
          </label>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {resumes.map((resume) => (
            <div 
              key={resume.id} 
              className="bg-white border-2 border-zinc-950 p-6 rounded-2xl hover:translate-y-[-2px] transition-all group relative overflow-hidden shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 bg-zinc-100 border-2 border-zinc-950 rounded-xl flex items-center justify-center text-zinc-900 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <FileText size={24} />
                </div>
                <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={() => handleDownload(resume)}
                    className="p-2 hover:bg-zinc-50 text-zinc-600 hover:text-zinc-900 border border-zinc-200 hover:border-zinc-300 rounded-lg transition-colors cursor-pointer"
                    title="Download/Print PDF"
                  >
                    <Download size={18} />
                  </button>
                  <button 
                    onClick={() => handleDelete(resume.id)}
                    className="p-2 hover:bg-red-50 text-zinc-600 hover:text-red-650 border border-zinc-200 hover:border-red-200 rounded-lg transition-colors cursor-pointer"
                    title="Delete resume"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>

              <h3 className="font-black text-lg text-zinc-950 mb-1 truncate pr-8" title={resume.name}>
                {resume.name}
              </h3>
              <p className="text-zinc-500 font-bold text-sm mb-4">
                Uploaded {new Date(resume.created_at).toLocaleDateString()}
              </p>

              <div className="flex items-center justify-between pt-4 border-t-2 border-zinc-100">
                <div className="flex items-center text-emerald-600 text-sm font-black">
                  <CheckCircle2 size={16} className="mr-1.5" />
                  <span>Parsed & Ready</span>
                </div>
                <span className="text-xs text-zinc-500 font-black">#{resume.id}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI Job Suggestions */}
      {suggestions.length > 0 && suggestions.map((group, groupIdx) => (
        <div key={groupIdx} className="mt-12 mb-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <h3 className="text-2xl font-black mb-4 flex items-center space-x-2 text-zinc-950 uppercase tracking-tight">
            <Loader2 className="text-zinc-900 animate-spin" size={20} />
            <span>AI Recommended Searches for: <span className="text-blue-700 font-black truncate max-w-[200px]">{group.resume_name}</span></span>
          </h3>
          <div className="flex flex-wrap gap-3">
            {group.suggestions.map((s: string, i: number) => (
              <button 
                key={i} 
                onClick={() => handleTagClick(s, group.resume_id)}
                className="px-5 py-3 bg-white border-2 border-zinc-950 rounded-xl text-zinc-900 hover:bg-zinc-50 transition-all cursor-pointer font-extrabold flex items-center space-x-2 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] group"
              >
                <span>{s}</span>
                <Search size={14} className="text-zinc-650 opacity-50 group-hover:opacity-100 transition-opacity" />
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Benefits Card */}
      <div className="mt-12 bg-white border-4 border-zinc-950 rounded-3xl p-8 flex flex-col md:flex-row items-center gap-8 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex-1">
          <h3 className="text-3xl font-black text-zinc-950 mb-3 uppercase tracking-tight">Optimize your AI Job Search</h3>
          <p className="text-zinc-700 font-bold mb-6 leading-relaxed">
            Our AI uses your resume to match you with the best opportunities. 
            Keep it updated to improve your match score and increase your chances of landing an interview.
          </p>
          <div className="flex flex-wrap items-center gap-6 text-sm font-black">
            <div className="flex items-center text-blue-700 bg-blue-50 px-3 py-1.5 rounded-full border border-blue-200">
              <div className="w-2.5 h-2.5 bg-blue-600 rounded-full mr-2" />
              Auto-tailored Cover Letters
            </div>
            <div className="flex items-center text-purple-700 bg-purple-50 px-3 py-1.5 rounded-full border border-purple-200">
              <div className="w-2.5 h-2.5 bg-purple-600 rounded-full mr-2" />
              Skill Gap Analysis
            </div>
          </div>
        </div>
        <div className="hidden lg:block shrink-0">
          <div className="w-32 h-32 bg-zinc-50 rounded-2xl flex items-center justify-center border-2 border-zinc-950 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] rotate-3">
             <FileText size={48} className="text-zinc-900" />
          </div>
        </div>
      </div>
    </div>
  );
}
