import { apiClient } from "./client";
import type {
  Project,
  ProjectActiveFilter,
  ProjectCreate,
  ProjectUpdate
} from "../types/project";

const projectPath = (workspaceId: string) => `/workspaces/${workspaceId}/projects`;

export async function listProjects(
  workspaceId: string,
  active: ProjectActiveFilter
): Promise<Project[]> {
  const response = await apiClient.get<Project[]>(projectPath(workspaceId), {
    params: active === null ? undefined : { active }
  });
  return response.data;
}

export async function createProject(
  workspaceId: string,
  project: ProjectCreate
): Promise<Project> {
  const response = await apiClient.post<Project>(projectPath(workspaceId), project);
  return response.data;
}

export async function updateProject(
  workspaceId: string,
  projectId: string,
  project: ProjectUpdate
): Promise<Project> {
  const response = await apiClient.patch<Project>(
    `${projectPath(workspaceId)}/${projectId}`,
    project
  );
  return response.data;
}

export async function activateProject(
  workspaceId: string,
  projectId: string
): Promise<Project> {
  const response = await apiClient.post<Project>(
    `${projectPath(workspaceId)}/${projectId}/activate`
  );
  return response.data;
}

export async function deactivateProject(
  workspaceId: string,
  projectId: string
): Promise<Project> {
  const response = await apiClient.post<Project>(
    `${projectPath(workspaceId)}/${projectId}/deactivate`
  );
  return response.data;
}
