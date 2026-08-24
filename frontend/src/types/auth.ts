export interface AuthenticatedUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  timezone: string;
  is_active?: boolean;
  is_verified?: boolean;
  created_at?: string;
  updated_at?: string;
  global_role?: "GLOBAL_ADMIN" | null;
}

export interface WorkspaceSummary {
  id: string;
  name: string;
  description: string | null;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegistrationPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export interface ProfileUpdatePayload {
  first_name?: string;
  last_name?: string;
  timezone?: string;
}
