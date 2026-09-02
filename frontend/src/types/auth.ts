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
  kind?: "PERSONAL" | "SHARED";
  lifecycle?: "ACTIVE" | "INACTIVE";
  visible_role?: "Propietario" | "Miembro";
  can_manage?: boolean;
  can_delete?: boolean;
  description?: string | null;
  timezone: string;
  color?: "GREEN" | "BLUE" | "PURPLE" | "ORANGE" | "RED" | "TEAL";
  icon?: "HOME" | "USERS" | "HEART" | "STAR" | "CALENDAR" | "BRIEFCASE";
  lock_version?: number;
  created_at?: string;
  updated_at?: string;
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
  turnstile_token?: string;
}

export interface ProfileUpdatePayload {
  first_name: string;
  last_name: string;
  timezone: string;
  lock_version: number;
}

export interface ProfileRead {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  timezone: string;
  lock_version: number;
}
