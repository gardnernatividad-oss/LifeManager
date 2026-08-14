import { apiClient } from "./client";
import type { CategoryTableParams, CategoryTableResponse, MasterTaskTableParams, MasterTaskTableResponse } from "../types/masterData";
import type { CategoryOption } from "../types/planningPendingItem";
import type { MasterTaskOption } from "../types/planningTask";
import { env } from "../utils/env";
const apiUrl = (path: string) => new URL(`/api/v1${path}`, env.apiBaseUrl).toString();
export async function listCategoryTable(params: CategoryTableParams): Promise<CategoryTableResponse> { return (await apiClient.get<CategoryTableResponse>(apiUrl("/categories"), { params })).data; }
export async function createCategoryTable(name: string): Promise<CategoryOption> { return (await apiClient.post<CategoryOption>(apiUrl("/categories"), { name })).data; }
export async function updateCategoryTable(id: string, name: string): Promise<CategoryOption> { return (await apiClient.patch<CategoryOption>(apiUrl(`/categories/${id}`), { name })).data; }
export async function deleteCategoryTable(id: string): Promise<void> { await apiClient.delete(apiUrl(`/categories/${id}`)); }
export async function listMasterTaskTable(params: MasterTaskTableParams): Promise<MasterTaskTableResponse> { return (await apiClient.get<MasterTaskTableResponse>(apiUrl("/master-tasks"), { params })).data; }
export async function createMasterTaskTable(name: string, categoryId: string): Promise<MasterTaskOption> { return (await apiClient.post<MasterTaskOption>(apiUrl("/master-tasks"), { name, category_id: categoryId })).data; }
export async function updateMasterTaskTable(id: string, name: string, categoryId: string): Promise<MasterTaskOption> { return (await apiClient.patch<MasterTaskOption>(apiUrl(`/master-tasks/${id}`), { name, category_id: categoryId })).data; }
export async function deleteMasterTaskTable(id: string): Promise<void> { await apiClient.delete(apiUrl(`/master-tasks/${id}`)); }
