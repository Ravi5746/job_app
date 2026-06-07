'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Globe, 
  Briefcase, 
  Building2, 
  CheckCircle2, 
  AlertCircle, 
  ExternalLink,
  ShieldCheck,
  User,
  Bell,
  Lock,
  Monitor,
  Trash2,
  GraduationCap,
  Award,
  Languages,
  Target,
  DollarSign,
  ChevronDown,
  ChevronUp,
  Plus,
  Save,
  CheckCircle,
  Edit3
} from 'lucide-react';
import api from '@/services/api';

const platforms = [
  {
    id: 'linkedin',
    name: 'LinkedIn',
    icon: Briefcase,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-zinc-950',
    description: 'Connect to auto-apply for LinkedIn Easy Apply jobs.',
  },
  {
    id: 'indeed',
    name: 'Indeed',
    icon: Globe,
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-zinc-950',
    description: 'Sync your Indeed account for faster form filling.',
  },
  {
    id: 'naukri',
    name: 'Naukri',
    icon: Building2,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    borderColor: 'border-zinc-950',
    description: 'Integrate with Naukri to automate Indian job applications.',
  },
  {
    id: 'glassdoor',
    name: 'Glassdoor',
    icon: Globe,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-zinc-950',
    description: 'Get AI-powered applications on Glassdoor listings.',
  }
];

interface QuestionAnswer {
  question: string;
  answer: string;
}

interface WorkExperience {
  company: string;
  role: string;
  start: string;
  end: string;
  description: string;
}

interface Education {
  degree: string;
  institution: string;
  year: string;
  field: string;
}

interface Certification {
  name: string;
  issuer: string;
  year: string;
}

interface ProfileData {
  full_name: string;
  email: string;
  phone: string;
  phone_country_code?: string;
  location: string;
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
  summary: string;
  skills: string[];
  work_experience: WorkExperience[];
  total_years_experience: number;
  education: Education[];
  certifications: Certification[];
  languages: string[];
  desired_job_titles: string[];
  expected_salary: string;
  notice_period: string;
  work_authorization: string;
  willing_to_relocate: boolean | null;
  questionnaire: QuestionAnswer[];
  completeness: number;
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'platforms' | 'profile'>('platforms');
  const [connecting, setConnecting] = useState<string | null>(null);
  const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<Record<string, string | boolean>>({});
  
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  
  const [customQuestion, setCustomQuestion] = useState('');
  const [newSkill, setNewSkill] = useState('');
  const [editingExpIdx, setEditingExpIdx] = useState<number | null>(null);
  const [editingEduIdx, setEditingEduIdx] = useState<number | null>(null);
  const [editingCertIdx, setEditingCertIdx] = useState<number | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    contact: true,
    skills: true,
    experience: false,
    education: false,
    certifications: false,
    preferences: true,
    questionnaire: false,
  });

  const mountedRef = useRef(true);

  const toggleSection = (key: string) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.get('/settings/status');
      if (mountedRef.current) {
        setConnectionStatus(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch connection status");
    }
  }, []);

  const fetchProfile = useCallback(async () => {
    try {
      setProfileLoading(true);
      const response = await api.get('/resumes/my-profile');
      if (mountedRef.current) {
        setProfile(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch profile settings", error);
    } finally {
      if (mountedRef.current) {
        setProfileLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchStatus();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchStatus]);

  const getCompleteness = (prof: ProfileData) => {
    const checkFields = [
      !!prof.full_name,
      !!prof.phone,
      !!prof.phone_country_code,
      !!prof.location,
      !!prof.summary,
      !!prof.linkedin_url,
      prof.skills.length > 0,
      prof.work_experience.length > 0,
      prof.education.length > 0,
      !!prof.expected_salary,
      !!prof.notice_period,
      !!prof.work_authorization,
    ];
    return Math.round((checkFields.filter(Boolean).length / checkFields.length) * 100);
  };

  const completeness = profile ? getCompleteness(profile) : 0;

  const formatSalaryLPA = (salary: string | undefined) => {
    if (!salary) return '';
    const cleanSalary = salary.replace(/,/g, '').replace(/ /g, '').trim();
    const num = parseInt(cleanSalary);
    if (isNaN(num) || num <= 0) return '';
    
    if (num >= 10000000) {
      return `(₹ ${(num / 10000000).toFixed(2)} Crore LPA)`;
    } else if (num >= 100000) {
      return `(₹ ${(num / 100000).toFixed(2)} Lakhs LPA)`;
    } else {
      return `(₹ ${num.toLocaleString('en-IN')} LPA)`;
    }
  };

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;

    // Validate expected salary strictly
    if (profile.expected_salary) {
      const cleanSalary = profile.expected_salary.replace(/,/g, '').replace(/ /g, '').trim();
      if (cleanSalary !== "" && !/^\d+$/.test(cleanSalary)) {
        setStatus({ type: 'error', message: 'Expected salary must be a positive number (e.g. 400000)' });
        return;
      }
    }

    try {
      setProfileSaving(true);
      setStatus(null);
      const response = await api.put('/resumes/my-profile', profile);
      if (mountedRef.current) {
        setProfile(response.data);
        setStatus({ type: 'success', message: 'Profile settings updated successfully.' });
        setTimeout(() => setStatus(null), 3000);
      }
    } catch (error: any) {
      console.error("Failed to save profile settings", error);
      if (mountedRef.current) {
        setStatus({ type: 'error', message: error.response?.data?.detail || 'Failed to save profile settings.' });
      }
    } finally {
      if (mountedRef.current) {
        setProfileSaving(false);
      }
    }
  };

  const addSkill = () => {
    if (!newSkill.trim() || !profile) return;
    setProfile({ ...profile, skills: [...profile.skills, newSkill.trim()] });
    setNewSkill('');
  };

  const removeSkill = (idx: number) => {
    if (!profile) return;
    setProfile({ ...profile, skills: profile.skills.filter((_, i) => i !== idx) });
  };

  const addCustomQuestion = () => {
    if (!customQuestion.trim() || !profile) return;
    setProfile({
      ...profile,
      questionnaire: [...profile.questionnaire, { question: customQuestion.trim(), answer: '' }]
    });
    setCustomQuestion('');
  };

  const updateQuestionAnswer = (idx: number, answer: string) => {
    if (!profile) return;
    const updated = [...profile.questionnaire];
    updated[idx] = { ...updated[idx], answer };
    setProfile({ ...profile, questionnaire: updated });
  };

  const updateWorkExperience = (index: number, field: keyof WorkExperience, value: string) => {
    if (!profile) return;
    const updated = [...profile.work_experience];
    updated[index] = { ...updated[index], [field]: value };
    setProfile({ ...profile, work_experience: updated });
  };

  const addWorkExperience = () => {
    if (!profile) return;
    const newExp: WorkExperience = {
      company: '',
      role: '',
      start: '',
      end: '',
      description: ''
    };
    const updated = [...profile.work_experience, newExp];
    setProfile({ ...profile, work_experience: updated });
    setEditingExpIdx(updated.length - 1);
  };

  const removeWorkExperience = (index: number) => {
    if (!profile) return;
    const updated = profile.work_experience.filter((_, i) => i !== index);
    setProfile({ ...profile, work_experience: updated });
    if (editingExpIdx === index) {
      setEditingExpIdx(null);
    } else if (editingExpIdx !== null && editingExpIdx > index) {
      setEditingExpIdx(editingExpIdx - 1);
    }
  };

  const updateEducation = (index: number, field: keyof Education, value: string) => {
    if (!profile) return;
    const updated = [...profile.education];
    updated[index] = { ...updated[index], [field]: value };
    setProfile({ ...profile, education: updated });
  };

  const addEducation = () => {
    if (!profile) return;
    const newEdu: Education = {
      degree: '',
      institution: '',
      year: '',
      field: ''
    };
    const updated = [...profile.education, newEdu];
    setProfile({ ...profile, education: updated });
    setEditingEduIdx(updated.length - 1);
  };

  const removeEducation = (index: number) => {
    if (!profile) return;
    const updated = profile.education.filter((_, i) => i !== index);
    setProfile({ ...profile, education: updated });
    if (editingEduIdx === index) {
      setEditingEduIdx(null);
    } else if (editingEduIdx !== null && editingEduIdx > index) {
      setEditingEduIdx(editingEduIdx - 1);
    }
  };

  const updateCertification = (index: number, field: keyof Certification, value: string) => {
    if (!profile) return;
    const updated = [...profile.certifications];
    updated[index] = { ...updated[index], [field]: value };
    setProfile({ ...profile, certifications: updated });
  };

  const addCertification = () => {
    if (!profile) return;
    const newCert: Certification = {
      name: '',
      issuer: '',
      year: ''
    };
    const updated = [...profile.certifications, newCert];
    setProfile({ ...profile, certifications: updated });
    setEditingCertIdx(updated.length - 1);
  };

  const removeCertification = (index: number) => {
    if (!profile) return;
    const updated = profile.certifications.filter((_, i) => i !== index);
    setProfile({ ...profile, certifications: updated });
    if (editingCertIdx === index) {
      setEditingCertIdx(null);
    } else if (editingCertIdx !== null && editingCertIdx > index) {
      setEditingCertIdx(editingCertIdx - 1);
    }
  };

  const handleDisconnect = async (platformId: string) => {
    try {
      const response = await api.post(`/settings/disconnect/${platformId}`);
      if (response.data.status === 'success') {
        setStatus({ type: 'success', message: `${platformId.charAt(0).toUpperCase() + platformId.slice(1)} disconnected.` });
        fetchStatus();
      }
    } catch (error) {
      setStatus({ type: 'error', message: 'Failed to disconnect.' });
    }
  };

  const handleDisconnectAll = async () => {
    if (!confirm("Are you sure you want to disconnect all platforms and wipe session data?")) return;
    try {
      const response = await api.post('/settings/disconnect-all');
      if (response.data.status === 'success') {
        setStatus({ type: 'success', message: 'All platforms disconnected.' });
        fetchStatus();
      }
    } catch (error) {
      setStatus({ type: 'error', message: 'Failed to disconnect all.' });
    }
  };

  const handleConnect = async (platformId: string) => {
    setConnecting(platformId);
    setStatus(null);
    try {
      const response = await api.post(`/settings/connect/${platformId}`);
      if (response.data.status === 'success') {
        setStatus({ type: 'success', message: `${platformId.charAt(0).toUpperCase() + platformId.slice(1)} connected successfully!` });
        fetchStatus(); // Refresh status
      } else {
        setStatus({ type: 'error', message: response.data.message });
      }
    } catch (error: any) {
      setStatus({ type: 'error', message: 'Failed to open connection window.' });
    } finally {
      setConnecting(null);
    }
  };

  const SectionHeader = ({ title, icon: Icon, section, badge }: { title: string; icon: any; section: string; badge?: string }) => (
    <button
      type="button"
      onClick={() => toggleSection(section)}
      className="w-full flex items-center justify-between p-4 bg-white border-2 border-zinc-950 rounded-2xl hover:bg-zinc-50 transition-all shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] cursor-pointer mt-4"
    >
      <div className="flex items-center space-x-3">
        <Icon size={18} className="text-zinc-700" />
        <span className="font-black text-zinc-900 text-xs uppercase tracking-wider">{title}</span>
        {badge && (
          <span className="px-2.5 py-0.5 bg-zinc-150 text-zinc-700 text-xs font-black rounded-full border-2 border-zinc-950 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">{badge}</span>
        )}
      </div>
      {expandedSections[section] ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
    </button>
  );

  const inputClass = "w-full bg-white border-2 border-zinc-950 rounded-xl p-3 text-zinc-900 font-semibold outline-none focus:ring-0 focus:border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]";
  const labelClass = "block text-xs font-black text-zinc-600 mb-1.5 uppercase tracking-wider";

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      <div className="flex items-center space-x-3 mb-8">
        <div className="p-2.5 bg-zinc-900 border-2 border-zinc-950 rounded-2xl shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
          <Globe className="w-6 h-6 text-white" />
        </div>
        <h1 className="text-4xl font-black text-zinc-950 tracking-tight">SETTINGS</h1>
      </div>

      {/* Tabs navigation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Sidebar Nav */}
        <div className="lg:col-span-1 space-y-3">
          <button 
            onClick={() => {
              setActiveTab('platforms');
              setStatus(null);
            }}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all font-bold border-2 text-sm ${
              activeTab === 'platforms' 
                ? 'bg-zinc-900 text-white border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]' 
                : 'text-zinc-600 border-transparent hover:bg-zinc-100 hover:text-zinc-900'
            }`}
          >
            <Globe className="w-5 h-5" />
            <span>Platform Connections</span>
          </button>
          <button 
            onClick={() => {
              setActiveTab('profile');
              setStatus(null);
              fetchProfile();
            }}
            className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all font-bold border-2 text-sm ${
              activeTab === 'profile' 
                ? 'bg-zinc-900 text-white border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]' 
                : 'text-zinc-600 border-transparent hover:bg-zinc-100 hover:text-zinc-900'
            }`}
          >
            <User className="w-5 h-5" />
            <span>Profile Settings</span>
          </button>
          <button 
            disabled 
            className="w-full flex items-center space-x-3 px-4 py-3 text-zinc-400 cursor-not-allowed rounded-xl font-bold text-sm border-2 border-transparent"
          >
            <Bell className="w-5 h-5" />
            <span>Notifications</span>
          </button>
          <button 
            disabled 
            className="w-full flex items-center space-x-3 px-4 py-3 text-zinc-400 cursor-not-allowed rounded-xl font-bold text-sm border-2 border-transparent"
          >
            <Lock className="w-5 h-5" />
            <span>Privacy & Security</span>
          </button>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-[2rem] border-2 border-zinc-950 p-8 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            
            {activeTab === 'platforms' ? (
              <>
                <div className="mb-8">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
                    <div>
                      <h2 className="text-2xl font-black text-zinc-950 uppercase tracking-tight">Platform Connections</h2>
                      <p className="text-sm text-zinc-600 font-semibold mt-1">Connect your professional accounts to enable one-click AI job applications.</p>
                    </div>
                    <button 
                      onClick={handleDisconnectAll}
                      className="flex items-center space-x-2 px-4 py-2 text-xs font-black text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 rounded-xl transition-all border-2 border-red-200 cursor-pointer shadow-[2px_2px_0px_0px_rgba(220,38,38,0.2)] hover:translate-y-[-1px]"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>Disconnect All Platforms</span>
                    </button>
                  </div>
                </div>

                {status && (
                  <div className={`mb-6 p-4 rounded-2xl flex items-center space-x-3 border-2 ${
                    status.type === 'success' ? 'bg-emerald-50 border-emerald-950 text-emerald-900' : 'bg-red-50 border-red-950 text-red-900'
                  }`}>
                    {status.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <AlertCircle className="w-5 h-5 text-red-600" />}
                    <p className="font-bold text-sm">{status.message}</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {platforms.map((platform) => (
                    <div 
                      key={platform.id}
                      className={`p-6 rounded-[1.5rem] border-2 border-zinc-950 bg-white transition-all shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-2px] group`}
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className={`p-3 rounded-xl bg-zinc-50 border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${platform.color}`}>
                          <platform.icon className="w-6 h-6" />
                        </div>
                        <div className="flex flex-col space-y-2">
                          <button
                            onClick={() => handleConnect(platform.id)}
                            disabled={connecting !== null}
                            className={`flex items-center justify-center space-x-2 px-4 py-2 rounded-xl text-xs font-black transition-all border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer ${
                              connectionStatus[platform.id]
                                ? 'bg-emerald-500 text-white shadow-none cursor-default active:translate-x-0 active:translate-y-0'
                                : connecting === platform.id
                                  ? 'bg-zinc-100 text-zinc-400 border-zinc-300 shadow-none cursor-not-allowed'
                                  : 'bg-zinc-900 text-white hover:bg-zinc-800'
                            }`}
                          >
                            {connectionStatus[platform.id] ? (
                              <>
                                <CheckCircle2 className="w-4 h-4" />
                                <span>Connected</span>
                              </>
                            ) : connecting === platform.id ? (
                              <>
                                <div className="w-4 h-4 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
                                <span>Connecting...</span>
                              </>
                            ) : (
                              <>
                                <ExternalLink className="w-4 h-4" />
                                <span>Connect</span>
                              </>
                            )}
                          </button>
                          
                          {connectionStatus[platform.id] && (
                            <button
                              onClick={() => handleDisconnect(platform.id)}
                              className="flex items-center justify-center space-x-2 px-3 py-1.5 rounded-lg text-2xs font-bold text-red-600 hover:bg-red-50 transition-all border border-transparent hover:border-red-150 cursor-pointer"
                            >
                              <Monitor className="w-3 h-3" />
                              <span>Disconnect</span>
                            </button>
                          )}
                        </div>
                      </div>
                      <h3 className="text-lg font-black text-zinc-950 mb-1 uppercase tracking-tight">{platform.name}</h3>
                      <div className="flex flex-col">
                        <p className="text-xs text-zinc-500 font-semibold mb-3 leading-relaxed">{platform.description}</p>
                        {connectionStatus[platform.id] && typeof connectionStatus[platform.id] === 'string' && (
                          <div className="flex items-center space-x-2 text-2xs font-black text-zinc-700 bg-zinc-100 border border-zinc-300 px-3 py-1.5 rounded-full w-fit">
                            <User className="w-3 h-3" />
                            <span>{connectionStatus[platform.id]}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-12 p-6 bg-zinc-50 rounded-2xl border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] flex items-start space-x-4">
                  <div className="p-2.5 bg-white rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] text-emerald-600 shrink-0">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="font-black text-zinc-950 uppercase tracking-tight text-sm">Security Guarantee</h4>
                    <p className="text-xs text-zinc-500 font-medium leading-relaxed mt-1">
                      We never store your passwords. When you connect a platform, the AI uses a local, isolated browser profile to securely manage your session. Your data never leaves your computer.
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-8 border-b-2 border-zinc-100 pb-6">
                  <div>
                    <h2 className="text-2xl font-black text-zinc-950 uppercase tracking-tight">Profile Settings</h2>
                    <p className="text-sm text-zinc-600 font-semibold mt-1">Review and manage your personal information used by the AI agent for job matching and applications.</p>
                  </div>
                  {profile && (
                    <div className="flex items-center space-x-3 shrink-0">
                      <div className="text-right">
                        <div className="text-2xs font-black text-zinc-400 uppercase tracking-wider">Completeness</div>
                        <div className="text-xl font-black text-zinc-950">{completeness}%</div>
                      </div>
                      <div className="w-10 h-10 relative">
                        <svg viewBox="0 0 36 36" className="w-10 h-10 -rotate-90">
                          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                            fill="none" stroke="#f4f4f5" strokeWidth="3" />
                          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                            fill="none" stroke={completeness >= 80 ? "#10b981" : completeness >= 50 ? "#f59e0b" : "#ef4444"}
                            strokeWidth="3" strokeDasharray={`${completeness}, 100`} strokeLinecap="round" />
                        </svg>
                      </div>
                    </div>
                  )}
                </div>

                {status && (
                  <div className={`mb-6 p-4 rounded-2xl flex items-center space-x-3 border-2 ${
                    status.type === 'success' ? 'bg-emerald-50 border-emerald-950 text-emerald-900' : 'bg-red-50 border-red-950 text-red-900'
                  }`}>
                    {status.type === 'success' ? <CheckCircle className="w-5 h-5 text-emerald-600" /> : <AlertCircle className="w-5 h-5 text-red-600" />}
                    <p className="font-bold text-sm">{status.message}</p>
                  </div>
                )}

                {profileLoading ? (
                  <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
                    <div className="w-10 h-10 border-4 border-zinc-950 border-t-transparent rounded-full animate-spin mb-4" />
                    <p className="font-black uppercase text-xs tracking-wider">Loading profile data...</p>
                  </div>
                ) : !profile ? (
                  <div className="py-10 text-center text-zinc-500 font-semibold">Failed to load profile. Please try again.</div>
                ) : (
                  <form onSubmit={handleProfileSave} className="space-y-4">
                    <div className="p-4 bg-zinc-50 border-2 border-zinc-950 rounded-2xl flex items-start space-x-3 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                      <AlertCircle className="w-5 h-5 text-zinc-700 shrink-0 mt-0.5" />
                      <p className="text-xs text-zinc-650 font-bold leading-relaxed">
                        <strong>AI RESUME EXTRACTION:</strong> These fields are automatically populated when you upload a resume on the Resumes page. You can adjust them manually below at any time.
                      </p>
                    </div>

                    {/* Contact Info */}
                    <SectionHeader title="Contact Information" icon={User} section="contact" />
                    {expandedSections.contact && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        <div>
                          <label className={labelClass}>Full Name</label>
                          <input type="text" value={profile.full_name || ''} onChange={e => setProfile({ ...profile, full_name: e.target.value })} className={inputClass} required />
                        </div>
                        <div>
                          <label className={labelClass}>Email Address</label>
                          <input type="email" value={profile.email || ''} onChange={e => setProfile({ ...profile, email: e.target.value })} className={inputClass} required />
                        </div>
                        <div>
                          <label className={labelClass}>Phone Number</label>
                          <div className="flex space-x-2">
                            <select
                              value={profile.phone_country_code || ""}
                              onChange={e => setProfile({ ...profile, phone_country_code: e.target.value })}
                              className={`${inputClass} !w-24 shrink-0`}
                            >
                              <option value="">Code</option>
                              <option value="+91">🇮🇳 +91</option>
                              <option value="+1">🇺🇸/🇨🇦 +1</option>
                              <option value="+44">🇬🇧 +44</option>
                              <option value="+61">🇦🇺 +61</option>
                              <option value="+971">🇦🇪 +971</option>
                              <option value="+49">🇩🇪 +49</option>
                              <option value="+33">🇫🇷 +33</option>
                              <option value="+81">🇯🇵 +81</option>
                              <option value="+65">🇸🇬 +65</option>
                              <option value="+86">🇨🇳 +86</option>
                            </select>
                            <input
                              type="tel"
                              placeholder="10-digit mobile"
                              value={profile.phone || ""}
                              onChange={e => {
                                const val = e.target.value.replace(/\D/g, "");
                                if (val.length <= 10) {
                                  setProfile({ ...profile, phone: val });
                                }
                              }}
                              className={inputClass}
                            />
                          </div>
                        </div>
                        <div>
                          <label className={labelClass}>Location</label>
                          <input type="text" value={profile.location || ''} onChange={e => setProfile({ ...profile, location: e.target.value })} className={inputClass} />
                        </div>
                        <div>
                          <label className={labelClass}>LinkedIn URL</label>
                          <input type="url" value={profile.linkedin_url || ''} onChange={e => setProfile({ ...profile, linkedin_url: e.target.value })} className={inputClass} />
                        </div>
                        <div>
                          <label className={labelClass}>GitHub URL</label>
                          <input type="url" value={profile.github_url || ''} onChange={e => setProfile({ ...profile, github_url: e.target.value })} className={inputClass} />
                        </div>
                        <div className="md:col-span-2">
                          <label className={labelClass}>Portfolio/Website URL</label>
                          <input type="text" value={profile.portfolio_url || 'NaN'} onChange={e => setProfile({ ...profile, portfolio_url: e.target.value })} className={inputClass} />
                        </div>
                        <div className="md:col-span-2">
                          <label className={labelClass}>Professional Summary</label>
                          <textarea rows={3} value={profile.summary || ''} onChange={e => setProfile({ ...profile, summary: e.target.value })} className={`${inputClass} resize-none`} />
                        </div>
                      </div>
                    )}

                    {/* Skills */}
                    <SectionHeader title="Skills" icon={Target} section="skills" badge={`${profile.skills?.length || 0} skills`} />
                    {expandedSections.skills && (
                      <div className="p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        <div className="flex flex-wrap gap-2 mb-4">
                          {(profile.skills || []).map((skill, idx) => (
                            <span key={idx} className="inline-flex items-center space-x-1 px-3 py-1.5 bg-white border-2 border-zinc-950 rounded-full text-xs font-black shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">
                              <span>{skill}</span>
                              <button type="button" onClick={() => removeSkill(idx)} className="text-zinc-400 hover:text-red-500 ml-1 cursor-pointer"><Trash2 size={12} /></button>
                            </span>
                          ))}
                          {(!profile.skills || profile.skills.length === 0) && (
                            <p className="text-zinc-500 text-xs font-semibold">No skills extracted yet. Upload a resume to auto-populate.</p>
                          )}
                        </div>
                        <div className="flex items-center space-x-2">
                          <input type="text" placeholder="Add a skill..." value={newSkill} onChange={e => setNewSkill(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }} className={`flex-1 ${inputClass}`} />
                          <button type="button" onClick={addSkill} className="px-4 py-3 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer">
                            <Plus size={16} />
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Experience */}
                    <SectionHeader title="Work Experience" icon={Briefcase} section="experience" badge={`${profile.work_experience?.length || 0} positions`} />
                    {expandedSections.experience && (
                      <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        {(!profile.work_experience || profile.work_experience.length === 0) && (
                          <p className="text-zinc-500 text-xs font-semibold">No experience data. Click Add to insert.</p>
                        )}
                        {(profile.work_experience || []).map((exp, idx) => (
                          <div key={idx} className="p-4 bg-white border-2 border-zinc-950 rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] space-y-3 relative">
                            {editingExpIdx === idx ? (
                              <div className="space-y-3">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div>
                                    <label className={labelClass}>Role / Job Title</label>
                                    <input type="text" placeholder="e.g. Senior Software Engineer" value={exp.role} onChange={e => updateWorkExperience(idx, 'role', e.target.value)} className={inputClass} />
                                  </div>
                                  <div>
                                    <label className={labelClass}>Company</label>
                                    <input type="text" placeholder="e.g. Google" value={exp.company} onChange={e => updateWorkExperience(idx, 'company', e.target.value)} className={inputClass} />
                                  </div>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div>
                                    <label className={labelClass}>Start Date</label>
                                    <input type="text" placeholder="e.g. Jan 2020" value={exp.start} onChange={e => updateWorkExperience(idx, 'start', e.target.value)} className={inputClass} />
                                  </div>
                                  <div>
                                    <label className={labelClass}>End Date</label>
                                    <input type="text" placeholder="e.g. Present or Dec 2022" value={exp.end} onChange={e => updateWorkExperience(idx, 'end', e.target.value)} className={inputClass} />
                                  </div>
                                </div>
                                <div>
                                  <label className={labelClass}>Description</label>
                                  <textarea rows={3} placeholder="Describe your key responsibilities and achievements..." value={exp.description} onChange={e => updateWorkExperience(idx, 'description', e.target.value)} className={`${inputClass} resize-none`} />
                                </div>
                                <div className="flex justify-end space-x-2 pt-2">
                                  <button type="button" onClick={() => setEditingExpIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer text-xs">
                                    Done
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div>
                                <div className="flex justify-between items-start">
                                  <div>
                                    <div className="font-black text-zinc-950 text-sm">{exp.role || <span className="text-zinc-400 italic">Untitled Role</span>}</div>
                                    <div className="text-xs font-black text-zinc-650 mt-0.5">{exp.company || <span className="text-zinc-400 italic">Unknown Company</span>}</div>
                                    <div className="text-2xs font-bold text-zinc-400 mt-1">{exp.start || 'N/A'} - {exp.end || 'N/A'}</div>
                                  </div>
                                  <div className="flex space-x-2">
                                    <button type="button" onClick={() => setEditingExpIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Position">
                                      <Edit3 size={12} className="text-zinc-700" />
                                    </button>
                                    <button type="button" onClick={() => removeWorkExperience(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Position">
                                      <Trash2 size={12} className="text-red-500" />
                                    </button>
                                  </div>
                                </div>
                                {exp.description && <p className="text-xs text-zinc-650 mt-2 font-semibold leading-relaxed border-t border-dashed border-zinc-200 pt-2">{exp.description}</p>}
                              </div>
                            )}
                          </div>
                        ))}
                        
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-3 border-t border-zinc-200">
                          <div className="flex items-center space-x-2 flex-1 max-w-xs">
                            <label className="text-xs font-black text-zinc-600 uppercase tracking-wider whitespace-nowrap">Total Experience (Years)</label>
                            <input type="number" min="0" max="60" value={profile.total_years_experience} onChange={e => setProfile({ ...profile, total_years_experience: Math.max(0, parseInt(e.target.value) || 0) })} className={`${inputClass} !py-1 text-center`} />
                          </div>
                          <button type="button" onClick={addWorkExperience} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer flex items-center space-x-2 text-xs">
                            <Plus size={14} />
                            <span>Add Position</span>
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Education */}
                    <SectionHeader title="Education" icon={GraduationCap} section="education" badge={`${profile.education?.length || 0}`} />
                    {expandedSections.education && (
                      <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        {(!profile.education || profile.education.length === 0) && (
                          <p className="text-zinc-500 text-xs font-semibold">No education data. Click Add to insert.</p>
                        )}
                        {(profile.education || []).map((edu, idx) => (
                          <div key={idx} className="p-4 bg-white border-2 border-zinc-950 rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] space-y-3 relative">
                            {editingEduIdx === idx ? (
                              <div className="space-y-3">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div>
                                    <label className={labelClass}>Degree</label>
                                    <input type="text" placeholder="e.g. Bachelor of Technology" value={edu.degree} onChange={e => updateEducation(idx, 'degree', e.target.value)} className={inputClass} />
                                  </div>
                                  <div>
                                    <label className={labelClass}>Field of Study</label>
                                    <input type="text" placeholder="e.g. Computer Science" value={edu.field} onChange={e => updateEducation(idx, 'field', e.target.value)} className={inputClass} />
                                  </div>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  <div>
                                    <label className={labelClass}>Institution</label>
                                    <input type="text" placeholder="e.g. Stanford University" value={edu.institution} onChange={e => updateEducation(idx, 'institution', e.target.value)} className={inputClass} />
                                  </div>
                                  <div>
                                    <label className={labelClass}>Year</label>
                                    <input type="text" placeholder="e.g. 2022" value={edu.year} onChange={e => updateEducation(idx, 'year', e.target.value)} className={inputClass} />
                                  </div>
                                </div>
                                <div className="flex justify-end space-x-2 pt-2">
                                  <button type="button" onClick={() => setEditingEduIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer text-xs">
                                    Done
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex justify-between items-start">
                                <div>
                                  <div className="font-black text-zinc-950 text-sm">{edu.degree || <span className="text-zinc-400 italic">No Degree Specified</span>} {edu.field && `in ${edu.field}`}</div>
                                  <div className="text-xs font-black text-zinc-650 mt-0.5">{edu.institution || <span className="text-zinc-400 italic">No Institution Specified</span>}</div>
                                  <div className="text-2xs font-bold text-zinc-400 mt-1">{edu.year || 'N/A'}</div>
                                </div>
                                <div className="flex space-x-2">
                                  <button type="button" onClick={() => setEditingEduIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Education">
                                    <Edit3 size={12} className="text-zinc-700" />
                                  </button>
                                  <button type="button" onClick={() => removeEducation(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Education">
                                    <Trash2 size={12} className="text-red-500" />
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                        <div className="flex justify-end pt-2">
                          <button type="button" onClick={addEducation} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer flex items-center space-x-2 text-xs">
                            <Plus size={14} />
                            <span>Add Education</span>
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Certifications */}
                    <SectionHeader title="Certifications" icon={Award} section="certifications" badge={`${profile.certifications?.length || 0}`} />
                    {expandedSections.certifications && (
                      <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        {(!profile.certifications || profile.certifications.length === 0) && (
                          <p className="text-zinc-500 text-xs font-semibold">No certifications found. Click Add to insert.</p>
                        )}
                        {(profile.certifications || []).map((cert, idx) => (
                          <div key={idx} className="p-4 bg-white border-2 border-zinc-950 rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] space-y-3 relative">
                            {editingCertIdx === idx ? (
                              <div className="space-y-3">
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                  <div className="md:col-span-2">
                                    <label className={labelClass}>Certification Name</label>
                                    <input type="text" placeholder="e.g. AWS Certified Solutions Architect" value={cert.name} onChange={e => updateCertification(idx, 'name', e.target.value)} className={inputClass} />
                                  </div>
                                  <div>
                                    <label className={labelClass}>Year</label>
                                    <input type="text" placeholder="e.g. 2023" value={cert.year} onChange={e => updateCertification(idx, 'year', e.target.value)} className={inputClass} />
                                  </div>
                                </div>
                                <div>
                                  <label className={labelClass}>Issuer</label>
                                  <input type="text" placeholder="e.g. Amazon Web Services" value={cert.issuer} onChange={e => updateCertification(idx, 'issuer', e.target.value)} className={inputClass} />
                                </div>
                                <div className="flex justify-end space-x-2 pt-2">
                                  <button type="button" onClick={() => setEditingCertIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer text-xs">
                                    Done
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex justify-between items-start">
                                <div>
                                  <div className="font-black text-zinc-950 text-sm">{cert.name || <span className="text-zinc-400 italic">Unnamed Certification</span>}</div>
                                  <div className="text-xs font-semibold text-zinc-650 mt-0.5">{cert.issuer || <span className="text-zinc-400 italic">Unknown Issuer</span>} {cert.year && `(${cert.year})`}</div>
                                </div>
                                <div className="flex space-x-2">
                                  <button type="button" onClick={() => setEditingCertIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Certification">
                                    <Edit3 size={12} className="text-zinc-700" />
                                  </button>
                                  <button type="button" onClick={() => removeCertification(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Certification">
                                    <Trash2 size={12} className="text-red-500" />
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                        <div className="flex justify-end pt-2">
                          <button type="button" onClick={addCertification} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer flex items-center space-x-2 text-xs">
                            <Plus size={14} />
                            <span>Add Certification</span>
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Preferences */}
                    <SectionHeader title="Job Preferences" icon={DollarSign} section="preferences" />
                    {expandedSections.preferences && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        <div>
                          <label className={labelClass}>
                            Expected Salary <span className="text-zinc-500 font-bold normal-case text-xs">{formatSalaryLPA(profile.expected_salary)}</span>
                          </label>
                          <input 
                            type="number" 
                            placeholder="e.g., 400000" 
                            min="0"
                            value={profile.expected_salary || ''}
                            onChange={e => {
                              const val = e.target.value;
                              if (val === '' || /^\d+$/.test(val)) {
                                setProfile({ ...profile, expected_salary: val });
                              }
                            }} 
                            className={inputClass} 
                          />
                          <p className="text-[10px] text-zinc-500 font-semibold mt-1">Required: Annual CTC in INR (digits only, e.g., 400000 for 4 Lakhs LPA)</p>
                        </div>
                        <div>
                          <label className={labelClass}>Notice Period</label>
                          <input type="text" placeholder="e.g., 30 days, Immediate" value={profile.notice_period || ''}
                            onChange={e => setProfile({ ...profile, notice_period: e.target.value })} className={inputClass} />
                        </div>
                        <div>
                          <label className={labelClass}>Work Authorization</label>
                          <input type="text" placeholder="e.g., Authorized to work, Need Sponsorship" value={profile.work_authorization || ''}
                            onChange={e => setProfile({ ...profile, work_authorization: e.target.value })} className={inputClass} />
                        </div>
                        <div>
                          <label className={labelClass}>Willing to Relocate</label>
                          <select value={profile.willing_to_relocate === null ? '' : profile.willing_to_relocate ? 'yes' : 'no'}
                            onChange={e => setProfile({ ...profile, willing_to_relocate: e.target.value === '' ? null : e.target.value === 'yes' })}
                            className={inputClass}>
                            <option value="">Not specified</option>
                            <option value="yes">Yes</option>
                            <option value="no">No</option>
                          </select>
                        </div>
                        <div className="md:col-span-2">
                          <label className={labelClass}>Languages Spoken</label>
                          <input type="text" placeholder="Comma separated: English, Hindi, ..." value={(profile.languages || []).join(', ')}
                            onChange={e => setProfile({ ...profile, languages: e.target.value.split(',').map(l => l.trim()).filter(Boolean) })}
                            className={inputClass} />
                        </div>
                      </div>
                    )}

                    {/* Questionnaire */}
                    <SectionHeader title="Interview Questionnaire" icon={ShieldCheck} section="questionnaire" badge={`${profile.questionnaire?.length || 0} questions`} />
                    {expandedSections.questionnaire && (
                      <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200 mt-2">
                        {(!profile.questionnaire || profile.questionnaire.length === 0) && (
                          <p className="text-zinc-500 text-xs font-semibold">No questionnaire questions available.</p>
                        )}
                        {(profile.questionnaire || []).map((qa, idx) => (
                          <div key={idx}>
                            <label className={labelClass}>{qa.question}</label>
                            <textarea rows={2} value={qa.answer || ''} onChange={e => updateQuestionAnswer(idx, e.target.value)}
                              className={`${inputClass} resize-none`} />
                          </div>
                        ))}
                        <div className="flex items-center space-x-2 pt-4 border-t border-zinc-300">
                          <input type="text" placeholder="Add a custom question..." value={customQuestion}
                            onChange={e => setCustomQuestion(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomQuestion(); } }}
                            className={`flex-1 ${inputClass}`} />
                          <button type="button" onClick={addCustomQuestion}
                            className="px-4 py-3 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] cursor-pointer">
                            Add
                          </button>
                        </div>
                      </div>
                    )}

                    <div className="flex justify-end pt-6 border-t-2 border-zinc-100 mt-6">
                      <button
                        type="submit"
                        disabled={profileSaving}
                        className="flex items-center space-x-2 px-8 py-3.5 rounded-xl text-sm font-black text-white bg-zinc-900 border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] hover:translate-y-[-1px] active:translate-y-[1px] active:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Save size={18} />
                        <span>{profileSaving ? 'Saving...' : 'Save Settings'}</span>
                      </button>
                    </div>
                  </form>
                )}
              </>
            )}

          </div>
        </div>

      </div>
    </div>
  );
}
