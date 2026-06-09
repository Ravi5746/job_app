import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: number;
  email: string;
  full_name: string;
  phone?: string;
  phone_country_code?: string;
  location?: string;
  linkedin_url?: string;
  github_url?: string;
  summary?: string;
  skills?: string[];
  work_experience?: any[];
  projects?: any[];
  total_years_experience?: number;
  education?: any[];
  certifications?: any[];
  gender?: string;
  disability_status?: string;
  desired_job_titles?: string[];
  expected_salary?: string;
  notice_period?: string;
  work_authorization?: string;
  requires_sponsorship?: boolean;
  country_of_citizenship?: string;
  willing_to_relocate?: boolean;
  languages?: string[];
  portfolio_url?: string;
  preferred_work_models?: string[];
  address_line_1?: string;
  address_line_2?: string;
  city?: string;
  state_province?: string;
  postal_code?: string;
  country?: string;
  questionnaire?: string[];
}

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (user, token) => set({ user, token }),
      logout: () => set({ user: null, token: null }),
    }),
    {
      name: 'auth-storage',
    }
  )
);
