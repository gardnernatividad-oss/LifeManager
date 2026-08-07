export interface Category {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CategoryCreate {
  name: string;
}

export interface CategoryUpdate {
  name: string;
}

export type CategoryActiveFilter = boolean | null;
