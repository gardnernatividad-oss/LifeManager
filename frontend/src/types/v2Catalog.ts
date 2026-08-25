export interface V2Category {
  id: string;
  workspace_id: string;
  name: string;
  is_active: boolean;
  lock_version: number;
  created_at: string;
  updated_at: string;
}

export interface V2CatalogItem extends V2Category {
  category_id: string;
  category_name: string;
}

export interface V2CatalogList<T> {
  items: T[];
  total: number;
}
