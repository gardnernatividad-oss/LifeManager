import { apiClient } from "./client";
import type {
  Category,
  CategoryActiveFilter,
  CategoryCreate,
  CategoryUpdate
} from "../types/category";

const categoryPath = (workspaceId: string) => `/workspaces/${workspaceId}/categories`;

export async function listCategories(
  workspaceId: string,
  active: CategoryActiveFilter
): Promise<Category[]> {
  const response = await apiClient.get<Category[]>(categoryPath(workspaceId), {
    params: active === null ? undefined : { active }
  });
  return response.data;
}

export async function createCategory(
  workspaceId: string,
  category: CategoryCreate
): Promise<Category> {
  const response = await apiClient.post<Category>(categoryPath(workspaceId), category);
  return response.data;
}

export async function updateCategory(
  workspaceId: string,
  categoryId: string,
  category: CategoryUpdate
): Promise<Category> {
  const response = await apiClient.patch<Category>(
    `${categoryPath(workspaceId)}/${categoryId}`,
    category
  );
  return response.data;
}

export async function activateCategory(
  workspaceId: string,
  categoryId: string
): Promise<Category> {
  const response = await apiClient.post<Category>(
    `${categoryPath(workspaceId)}/${categoryId}/activate`
  );
  return response.data;
}

export async function deactivateCategory(
  workspaceId: string,
  categoryId: string
): Promise<Category> {
  const response = await apiClient.post<Category>(
    `${categoryPath(workspaceId)}/${categoryId}/deactivate`
  );
  return response.data;
}
