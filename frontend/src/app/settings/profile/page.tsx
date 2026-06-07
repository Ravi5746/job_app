"use client";
import React, { useEffect, useState } from 'react';
import api from '@/services/api';
import {
  User, Briefcase, GraduationCap, Award, Languages, Target,
  DollarSign, Clock, Shield, MapPin, ChevronDown, ChevronUp,
  Plus, Trash2, Save, CheckCircle, Edit3, Folder
} from 'lucide-react';

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

interface Project {
  name: string;
  description: string;
  technologies: string[];
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
  projects?: Project[];
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

export default function ProfileSettings() {
  const [hasMounted, setHasMounted] = useState(false);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [customQuestion, setCustomQuestion] = useState('');
  const [newSkill, setNewSkill] = useState('');
  const [editingExpIdx, setEditingExpIdx] = useState<number | null>(null);
  const [editingProjIdx, setEditingProjIdx] = useState<number | null>(null);
  const [editingEduIdx, setEditingEduIdx] = useState<number | null>(null);
  const [editingCertIdx, setEditingCertIdx] = useState<number | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    contact: true,
    skills: true,
    experience: false,
    projects: false,
    education: false,
    certifications: false,
    preferences: true,
    questionnaire: false,
  });

  useEffect(() => {
    setHasMounted(true);
    const fetchProfile = async () => {
      try {
        const res = await api.get('/resumes/my-profile');
        setProfile(res.data);
      } catch (err) {
        console.error('Failed to load profile:', err);
      }
    };
    fetchProfile();
  }, []);

  const toggleSection = (key: string) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = async () => {
    if (!profile) return;

    // Validate expected salary strictly
    if (profile.expected_salary) {
      const cleanSalary = profile.expected_salary.replace(/,/g, '').replace(/ /g, '').trim();
      if (cleanSalary !== "" && !/^\d+$/.test(cleanSalary)) {
        setSaveMessage('Expected salary must be a positive number (e.g. 400000)');
        return;
      }
    }

    setIsSaving(true);
    setSaveMessage('');
    try {
      await api.put('/resumes/my-profile', profile);
      setSaveMessage('Profile saved successfully!');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (err: any) {
      console.error('Save error', err);
      const detail = err.response?.data?.detail;
      setSaveMessage(typeof detail === 'string' ? detail : 'Failed to save profile');
    } finally {
      setIsSaving(false);
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
      (prof.projects || []).length > 0,
      prof.education.length > 0,
      !!prof.expected_salary,
      !!prof.notice_period,
      !!prof.work_authorization,
    ];
    return Math.round((checkFields.filter(Boolean).length / checkFields.length) * 100);
  };

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

  const updateProject = (index: number, field: keyof Project, value: any) => {
    if (!profile) return;
    const updated = [...(profile.projects || [])];
    updated[index] = { ...updated[index], [field]: value };
    setProfile({ ...profile, projects: updated });
  };

  const addProject = () => {
    if (!profile) return;
    const newProj: Project = {
      name: '',
      description: '',
      technologies: []
    };
    const updated = [...(profile.projects || []), newProj];
    setProfile({ ...profile, projects: updated });
    setEditingProjIdx(updated.length - 1);
  };

  const removeProject = (index: number) => {
    if (!profile) return;
    const updated = (profile.projects || []).filter((_, i) => i !== index);
    setProfile({ ...profile, projects: updated });
    if (editingProjIdx === index) {
      setEditingProjIdx(null);
    } else if (editingProjIdx !== null && editingProjIdx > index) {
      setEditingProjIdx(editingProjIdx - 1);
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

  if (!hasMounted || !profile) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-lg font-black text-zinc-600">Loading profile...</span>
      </div>
    );
  }

  const completeness = profile ? getCompleteness(profile) : 0;

  const SectionHeader = ({ title, icon: Icon, section, badge }: { title: string; icon: any; section: string; badge?: string }) => (
    <button
      onClick={() => toggleSection(section)}
      className="w-full flex items-center justify-between p-4 bg-white border-2 border-zinc-950 rounded-xl hover:bg-zinc-50 transition-all shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] cursor-pointer"
    >
      <div className="flex items-center space-x-3">
        <Icon size={20} className="text-zinc-700" />
        <span className="font-black text-zinc-900 text-sm uppercase tracking-wider">{title}</span>
        {badge && (
          <span className="px-2 py-0.5 bg-zinc-100 text-zinc-600 text-xs font-bold rounded-full border border-zinc-200">{badge}</span>
        )}
      </div>
      {expandedSections[section] ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
    </button>
  );

  const inputClass = "w-full bg-white border-2 border-zinc-950 rounded-xl p-2.5 text-zinc-900 font-semibold outline-none focus:ring-0 focus:border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]";
  const labelClass = "block text-xs font-black text-zinc-600 mb-1.5 uppercase tracking-wider";

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      {/* Header with completeness */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-black text-zinc-950 tracking-tight">Profile Settings</h1>
        <div className="flex items-center space-x-3">
          <div className="text-right">
            <div className="text-xs font-bold text-zinc-500 uppercase">Completeness</div>
            <div className="text-2xl font-black text-zinc-950">{completeness}%</div>
          </div>
          <div className="w-12 h-12 relative">
            <svg viewBox="0 0 36 36" className="w-12 h-12 -rotate-90">
              <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none" stroke="#e4e4e7" strokeWidth="3" />
              <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none" stroke={completeness >= 80 ? "#22c55e" : completeness >= 50 ? "#f59e0b" : "#ef4444"}
                strokeWidth="3" strokeDasharray={`${completeness}, 100`} strokeLinecap="round" />
            </svg>
          </div>
        </div>
      </div>

      {/* Contact Info */}
      <SectionHeader title="Contact Information" icon={User} section="contact" />
      {expandedSections.contact && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          <div>
            <label className={labelClass}>Full Name</label>
            <input type="text" value={profile.full_name} onChange={e => setProfile({ ...profile, full_name: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Email</label>
            <input type="email" value={profile.email} onChange={e => setProfile({ ...profile, email: e.target.value })} className={inputClass} />
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
            <input type="text" value={profile.location} onChange={e => setProfile({ ...profile, location: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>LinkedIn URL</label>
            <input type="url" value={profile.linkedin_url} onChange={e => setProfile({ ...profile, linkedin_url: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>GitHub URL</label>
            <input type="url" value={profile.github_url} onChange={e => setProfile({ ...profile, github_url: e.target.value })} className={inputClass} />
          </div>
          <div className="md:col-span-2">
            <label className={labelClass}>Portfolio URL</label>
            <input type="text" value={profile.portfolio_url || 'NaN'} onChange={e => setProfile({ ...profile, portfolio_url: e.target.value })} className={inputClass} />
          </div>
          <div className="md:col-span-2">
            <label className={labelClass}>Professional Summary</label>
            <textarea rows={3} value={profile.summary} onChange={e => setProfile({ ...profile, summary: e.target.value })}
              className={`${inputClass} resize-none`} />
          </div>
        </div>
      )}

      {/* Skills */}
      <SectionHeader title="Skills" icon={Target} section="skills" badge={`${profile.skills.length} skills`} />
      {expandedSections.skills && (
        <div className="p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          <div className="flex flex-wrap gap-2 mb-4">
            {profile.skills.map((skill, idx) => (
              <span key={idx} className="inline-flex items-center space-x-1 px-3 py-1.5 bg-white border-2 border-zinc-950 rounded-full text-sm font-bold shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]">
                <span>{skill}</span>
                <button onClick={() => removeSkill(idx)} className="text-zinc-400 hover:text-red-500 ml-1 cursor-pointer"><Trash2 size={12} /></button>
              </span>
            ))}
            {profile.skills.length === 0 && <p className="text-zinc-500 text-sm font-semibold">No skills extracted yet. Upload a resume to auto-populate.</p>}
          </div>
          <div className="flex items-center space-x-2">
            <input type="text" placeholder="Add a skill..." value={newSkill} onChange={e => setNewSkill(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addSkill()} className={`flex-1 ${inputClass}`} />
            <button onClick={addSkill} className="px-4 py-2.5 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer">
              <Plus size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Work Experience */}
      <SectionHeader title="Work Experience" icon={Briefcase} section="experience" badge={`${profile.work_experience.length} positions`} />
      {expandedSections.experience && (
        <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          {profile.work_experience.length === 0 && <p className="text-zinc-500 text-sm font-semibold">No experience data. Click Add to insert.</p>}
          {profile.work_experience.map((exp, idx) => (
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
                    <button onClick={() => setEditingExpIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer text-xs">
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-black text-zinc-950 text-base">{exp.role || <span className="text-zinc-400 italic">Untitled Role</span>}</div>
                      <div className="text-sm font-semibold text-zinc-600">{exp.company || <span className="text-zinc-400 italic">Unknown Company</span>}</div>
                      <div className="text-xs font-bold text-zinc-400 mt-1">{exp.start || 'N/A'} - {exp.end || 'N/A'}</div>
                    </div>
                    <div className="flex space-x-2">
                      <button onClick={() => setEditingExpIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Position">
                        <Edit3 size={14} className="text-zinc-700" />
                      </button>
                      <button onClick={() => removeWorkExperience(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Position">
                        <Trash2 size={14} className="text-red-500" />
                      </button>
                    </div>
                  </div>
                  {exp.description && <p className="text-sm text-zinc-600 mt-3 font-semibold border-t border-dashed border-zinc-200 pt-2">{exp.description}</p>}
                </div>
              )}
            </div>
          ))}
          
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-3 border-t border-zinc-200">
            <div className="flex items-center space-x-2 flex-1 max-w-xs">
              <label className="text-xs font-black text-zinc-600 uppercase tracking-wider whitespace-nowrap">Total Experience (Years)</label>
              <input type="number" min="0" max="60" value={profile.total_years_experience} onChange={e => setProfile({ ...profile, total_years_experience: Math.max(0, parseInt(e.target.value) || 0) })} className={`${inputClass} !py-1 text-center`} />
            </div>
            <button onClick={addWorkExperience} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer flex items-center space-x-2 text-xs">
              <Plus size={14} />
              <span>Add Position</span>
            </button>
          </div>
        </div>
      )}

      {/* Projects */}
      <SectionHeader title="Projects" icon={Folder} section="projects" badge={`${(profile.projects || []).length} projects`} />
      {expandedSections.projects && (
        <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          {(profile.projects || []).length === 0 && <p className="text-zinc-500 text-sm font-semibold">No project data. Click Add to insert.</p>}
          {(profile.projects || []).map((proj, idx) => (
            <div key={idx} className="p-4 bg-white border-2 border-zinc-950 rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] space-y-3 relative">
              {editingProjIdx === idx ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label className={labelClass}>Project Name</label>
                      <input type="text" placeholder="e.g. ShopVerse" value={proj.name} onChange={e => updateProject(idx, 'name', e.target.value)} className={inputClass} />
                    </div>
                  </div>
                  <div>
                    <label className={labelClass}>Description</label>
                    <textarea rows={3} placeholder="Describe what you built and key achievements..." value={proj.description} onChange={e => updateProject(idx, 'description', e.target.value)} className={`${inputClass} resize-none`} />
                  </div>
                  <div>
                    <label className={labelClass}>Technologies (comma separated)</label>
                    <input type="text" placeholder="e.g. Python, React, FastAPI" value={(proj.technologies || []).join(', ')} onChange={e => updateProject(idx, 'technologies', e.target.value.split(',').map((t: string) => t.trim()).filter(Boolean))} className={inputClass} />
                  </div>
                  <div className="flex justify-end space-x-2 pt-2">
                    <button onClick={() => setEditingProjIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer text-xs">
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-black text-zinc-950 text-base">{proj.name || <span className="text-zinc-400 italic">Untitled Project</span>}</div>
                      {proj.technologies && proj.technologies.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {proj.technologies.map((tech, tIdx) => (
                            <span key={tIdx} className="text-[10px] bg-zinc-100 text-zinc-800 font-bold px-2 py-0.5 rounded border border-zinc-200">{tech}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex space-x-2">
                      <button onClick={() => setEditingProjIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Project">
                        <Edit3 size={14} className="text-zinc-700" />
                      </button>
                      <button onClick={() => removeProject(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Project">
                        <Trash2 size={14} className="text-red-500" />
                      </button>
                    </div>
                  </div>
                  {proj.description && <p className="text-sm text-zinc-600 mt-3 font-semibold border-t border-dashed border-zinc-200 pt-2">{proj.description}</p>}
                </div>
              )}
            </div>
          ))}
          <div className="flex justify-end pt-2">
            <button onClick={addProject} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer flex items-center space-x-2 text-xs">
              <Plus size={14} />
              <span>Add Project</span>
            </button>
          </div>
        </div>
      )}

      {/* Education */}
      <SectionHeader title="Education" icon={GraduationCap} section="education" badge={`${profile.education.length}`} />
      {expandedSections.education && (
        <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          {profile.education.length === 0 && <p className="text-zinc-500 text-sm font-semibold">No education data. Click Add to insert.</p>}
          {profile.education.map((edu, idx) => (
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
                    <button onClick={() => setEditingEduIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer text-xs">
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-black text-zinc-950 text-base">{edu.degree || <span className="text-zinc-400 italic">No Degree Specified</span>} {edu.field && `in ${edu.field}`}</div>
                    <div className="text-sm font-semibold text-zinc-600">{edu.institution || <span className="text-zinc-400 italic">No Institution Specified</span>}</div>
                    <div className="text-xs font-bold text-zinc-400">{edu.year || 'N/A'}</div>
                  </div>
                  <div className="flex space-x-2">
                    <button onClick={() => setEditingEduIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Education">
                      <Edit3 size={14} className="text-zinc-700" />
                    </button>
                    <button onClick={() => removeEducation(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Education">
                      <Trash2 size={14} className="text-red-500" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          <div className="flex justify-end pt-2">
            <button onClick={addEducation} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer flex items-center space-x-2 text-xs">
              <Plus size={14} />
              <span>Add Education</span>
            </button>
          </div>
        </div>
      )}

      {/* Certifications */}
      <SectionHeader title="Certifications" icon={Award} section="certifications" badge={`${profile.certifications.length}`} />
      {expandedSections.certifications && (
        <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          {profile.certifications.length === 0 && <p className="text-zinc-500 text-sm font-semibold">No certifications found. Click Add to insert.</p>}
          {profile.certifications.map((cert, idx) => (
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
                    <button onClick={() => setEditingCertIdx(null)} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer text-xs">
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-black text-zinc-950 text-base">{cert.name || <span className="text-zinc-400 italic">Unnamed Certification</span>}</div>
                    <div className="text-sm font-semibold text-zinc-600">{cert.issuer || <span className="text-zinc-400 italic">Unknown Issuer</span>} {cert.year && `(${cert.year})`}</div>
                  </div>
                  <div className="flex space-x-2">
                    <button onClick={() => setEditingCertIdx(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-zinc-100 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Edit Certification">
                      <Edit3 size={14} className="text-zinc-700" />
                    </button>
                    <button onClick={() => removeCertification(idx)} className="p-2 bg-white border-2 border-zinc-950 rounded-lg hover:bg-red-50 hover:border-red-500 hover:text-red-500 shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] cursor-pointer" title="Delete Certification">
                      <Trash2 size={14} className="text-red-500" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          <div className="flex justify-end pt-2">
            <button onClick={addCertification} className="px-4 py-2 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[0px_0px_0px_0px_rgba(0,0,0,1)] cursor-pointer flex items-center space-x-2 text-xs">
              <Plus size={14} />
              <span>Add Certification</span>
            </button>
          </div>
        </div>
      )}

      {/* Job Preferences */}
      <SectionHeader title="Job Preferences" icon={DollarSign} section="preferences" />
      {expandedSections.preferences && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          <div>
            <label className={labelClass}>
              Expected Salary <span className="text-zinc-500 font-bold normal-case text-xs">{formatSalaryLPA(profile.expected_salary)}</span>
            </label>
            <input 
              type="text" 
              placeholder="e.g., 400000" 
              value={profile.expected_salary}
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
            <input type="text" placeholder="e.g., 30 days, Immediate" value={profile.notice_period}
              onChange={e => setProfile({ ...profile, notice_period: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Work Authorization</label>
            <input type="text" placeholder="e.g., Authorized to work" value={profile.work_authorization}
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
            <label className={labelClass}>Languages</label>
            <input type="text" placeholder="Comma separated: English, Hindi, ..." value={(profile.languages || []).join(', ')}
              onChange={e => setProfile({ ...profile, languages: e.target.value.split(',').map(l => l.trim()).filter(Boolean) })}
              className={inputClass} />
          </div>
        </div>
      )}

      {/* Questionnaire */}
      <SectionHeader title="Interview Questionnaire" icon={Shield} section="questionnaire" badge={`${profile.questionnaire.length} questions`} />
      {expandedSections.questionnaire && (
        <div className="space-y-4 p-4 bg-zinc-50 rounded-xl border-2 border-zinc-200">
          {profile.questionnaire.length === 0 && <p className="text-zinc-500 text-sm font-semibold">No questionnaire data.</p>}
          {profile.questionnaire.map((qa, idx) => (
            <div key={idx}>
              <label className={labelClass}>{qa.question}</label>
              <textarea rows={2} value={qa.answer} onChange={e => updateQuestionAnswer(idx, e.target.value)}
                className={`${inputClass} resize-none`} />
            </div>
          ))}
          <div className="flex items-center space-x-2 pt-4 border-t border-zinc-300">
            <input type="text" placeholder="Add a custom question..." value={customQuestion}
              onChange={e => setCustomQuestion(e.target.value)} onKeyDown={e => e.key === 'Enter' && addCustomQuestion()}
              className={`flex-1 ${inputClass}`} />
            <button onClick={addCustomQuestion}
              className="px-4 py-2.5 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] cursor-pointer">
              Add
            </button>
          </div>
        </div>
      )}

      {/* Save Button */}
      <div className="flex items-center justify-between pt-4 border-t-2 border-zinc-200">
        {saveMessage && (
          <div className={`flex items-center space-x-2 text-sm font-bold ${saveMessage.includes('success') ? 'text-emerald-600' : 'text-red-600'}`}>
            {saveMessage.includes('success') && <CheckCircle size={16} />}
            <span>{saveMessage}</span>
          </div>
        )}
        <div className="flex-1" />
        <button onClick={handleSave} disabled={isSaving}
          className="px-8 py-3 bg-zinc-900 text-white font-black rounded-xl border-2 border-zinc-950 shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] disabled:opacity-50 transition-all flex items-center space-x-2 cursor-pointer">
          <Save size={18} />
          <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
        </button>
      </div>
    </div>
  );
}
