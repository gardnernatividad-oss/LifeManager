export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description: string | null;
}

export interface ProjectUpdate {
  name: string;
  description: string | null;
}

export type ProjectActiveFilter = boolean | null;
