import { apiClient } from "./client";
import type { WorkspaceSummary } from "../types/auth";
import { env } from "../utils/env";

const v2 = (path: string) => new URL(`/api/v2${path}`, env.apiBaseUrl).toString();

export interface WorkspaceMemberSummary {
  user_id: string;
  display_name: string;
  email: string;
  role: "Propietario" | "Miembro";
  status: "ACTIVE" | "LEFT" | "REMOVED";
  joined_at: string;
  ended_at: string | null;
}

export interface WorkspaceInvitationSummary {
  id: string;
  workspace_id: string;
  workspace_name: string;
  recipient_email: string;
  status: "PENDING" | "ACCEPTED" | "REJECTED" | "EXPIRED" | "CANCELLED";
  expires_at: string;
  created_at: string;
}

export interface ResponsibilityDirective {
  action: "REASSIGN" | "DELETE";
  target_user_id?: string;
}

export interface MemberExitResolution {
  delete_all?: boolean;
  tasks?: ResponsibilityDirective;
  pending_items?: ResponsibilityDirective;
  projects?: ResponsibilityDirective;
  project_stages?: ResponsibilityDirective;
}

export async function listWorkspaces(): Promise<WorkspaceSummary[]> {
  const response = await apiClient.get<WorkspaceSummary[]>(v2("/workspaces"));
  return response.data;
}

export async function listManagedWorkspaces(): Promise<WorkspaceSummary[]> {
  return (await apiClient.get<WorkspaceSummary[]>(v2("/workspaces/management"))).data;
}

export async function createSharedWorkspace(name: string): Promise<WorkspaceSummary> {
  return (await apiClient.post<WorkspaceSummary>(v2("/workspaces"), { name })).data;
}

export async function getWorkspaceLifecycle(id: string): Promise<WorkspaceSummary> {
  return (await apiClient.get<WorkspaceSummary>(v2(`/workspaces/${id}/lifecycle`))).data;
}

export async function deactivateWorkspace(id: string): Promise<WorkspaceSummary> {
  return (await apiClient.post<WorkspaceSummary>(v2(`/workspaces/${id}/deactivate`))).data;
}

export async function reactivateWorkspace(id: string): Promise<WorkspaceSummary> {
  return (await apiClient.post<WorkspaceSummary>(v2(`/workspaces/${id}/reactivate`))).data;
}

export async function deleteWorkspace(id: string): Promise<void> {
  await apiClient.delete(v2(`/workspaces/${id}`));
}

export async function listWorkspaceMembers(id: string): Promise<WorkspaceMemberSummary[]> {
  return (await apiClient.get<WorkspaceMemberSummary[]>(v2(`/workspaces/${id}/members`))).data;
}

export async function removeWorkspaceMember(id: string, userId: string, resolution?: MemberExitResolution): Promise<WorkspaceMemberSummary> {
  return (await apiClient.delete<WorkspaceMemberSummary>(v2(`/workspaces/${id}/members/${userId}`), { data: resolution })).data;
}

export async function leaveWorkspace(id: string, resolution?: MemberExitResolution): Promise<WorkspaceMemberSummary> {
  return (await apiClient.post<WorkspaceMemberSummary>(v2(`/workspaces/${id}/leave`), resolution)).data;
}

export async function transferWorkspaceOwnership(id: string, targetUserId: string): Promise<WorkspaceSummary> {
  return (await apiClient.post<WorkspaceSummary>(v2(`/workspaces/${id}/transfer-ownership`), { target_user_id: targetUserId })).data;
}

export async function listWorkspaceInvitations(id: string): Promise<WorkspaceInvitationSummary[]> {
  return (await apiClient.get<WorkspaceInvitationSummary[]>(v2(`/workspaces/${id}/invitations`))).data;
}

export async function listMyWorkspaceInvitations(): Promise<WorkspaceInvitationSummary[]> {
  return (await apiClient.get<WorkspaceInvitationSummary[]>(v2("/workspace-invitations"))).data;
}

export async function createWorkspaceInvitation(id: string, email: string): Promise<WorkspaceInvitationSummary> {
  return (await apiClient.post<WorkspaceInvitationSummary>(v2(`/workspaces/${id}/invitations`), { email })).data;
}

export async function actOnWorkspaceInvitation(id: string, action: "accept" | "reject" | "cancel"): Promise<WorkspaceInvitationSummary> {
  return (await apiClient.post<WorkspaceInvitationSummary>(v2(`/workspace-invitations/${id}/${action}`))).data;
}
