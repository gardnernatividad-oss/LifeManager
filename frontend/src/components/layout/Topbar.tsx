import type { RefObject } from "react";

import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";

interface TopbarProps {
  isMenuOpen: boolean;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
  onMenuToggle: () => void;
}

export function Topbar({ isMenuOpen, menuButtonRef, onMenuToggle }: TopbarProps) {
  const { setWorkspace, user, workspace } = useAuth();
  const workspacesQuery = useWorkspaces();
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ");

  function handleWorkspaceChange(workspaceId: string) {
    const selectedWorkspace = workspacesQuery.data?.find(
      (candidate) => candidate.id === workspaceId
    );
    if (selectedWorkspace) setWorkspace(selectedWorkspace);
  }

  return (
    <header className="topbar">
      <div className="topbar__workspace">
        <button
          ref={menuButtonRef}
          className="topbar__menu-button"
          type="button"
          aria-label={isMenuOpen ? "Cerrar menú de navegación" : "Abrir menú de navegación"}
          aria-controls="application-sidebar"
          aria-expanded={isMenuOpen}
          onClick={onMenuToggle}
        >
          <span aria-hidden="true">☰</span>
        </button>
        <div>
          <span className="topbar__label" id="workspace-selector-label">
            Espacio de trabajo
          </span>
          {workspacesQuery.data && workspacesQuery.data.length > 1 ? (
            <select
              className="topbar__workspace-select"
              id="workspace-selector"
              aria-labelledby="workspace-selector-label"
              value={workspace?.id ?? ""}
              onChange={(event) => handleWorkspaceChange(event.target.value)}
            >
              {workspacesQuery.data.map((availableWorkspace) => (
                <option key={availableWorkspace.id} value={availableWorkspace.id}>
                  {availableWorkspace.name}
                </option>
              ))}
            </select>
          ) : (
            <strong>
              {workspacesQuery.isPending
                ? "Cargando…"
                : workspacesQuery.isError
                  ? "No disponible"
                  : workspace?.name ?? "Sin espacio"}
            </strong>
          )}
        </div>
      </div>
      <div className="topbar__user" aria-label="Usuario actual">
        <span className="topbar__avatar" aria-hidden="true">
          {user?.first_name?.charAt(0).toUpperCase() ?? "U"}
        </span>
        <span className="topbar__identity">
          <strong>{fullName || user?.email}</strong>
          <span>{user?.email}</span>
        </span>
      </div>
    </header>
  );
}
