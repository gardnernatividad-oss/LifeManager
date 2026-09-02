export type AccountStatus =
  | "PENDING_EMAIL_VERIFICATION"
  | "PENDING_APPROVAL"
  | "ACTIVE"
  | "REJECTED"
  | "DISABLED";

export interface AdminAccountRequest {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  timezone: string;
  account_status: AccountStatus;
  email_verified_at: string | null;
  created_at: string;
}

export interface AdminAccountRequestList {
  items: AdminAccountRequest[];
  total: number;
}

export interface AdminUser extends AdminAccountRequest {
  global_role: "GLOBAL_ADMIN" | null;
  status_changed_at: string;
  lock_version: number;
}

export interface AdminUserList {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminUserFilters {
  page: number;
  page_size: number;
  account_status?: AccountStatus;
  search?: string;
}
