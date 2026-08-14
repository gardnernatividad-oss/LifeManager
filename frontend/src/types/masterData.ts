import type { CategoryOption } from "./planningPendingItem";
import type { MasterTaskOption } from "./planningTask";
export interface CategoryTableParams { page: number; page_size: number }
export interface CategoryTableResponse { items: CategoryOption[]; total: number; page: number; page_size: number; total_pages: number }
export interface MasterTaskTableParams { page: number; page_size: number; category_id?: string }
export interface MasterTaskTableResponse { items: MasterTaskOption[]; total: number; page: number; page_size: number; total_pages: number }
