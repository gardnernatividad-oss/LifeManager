import type { RefObject } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

const navigation = [
  ["Dashboard", "/dashboard", "⌂"],
  ["Tasks", "/tasks", "✓"],
  ["Recurring Tasks", "/tasks/recurring", "↻"],
  ["Projects", "/projects", "▣"],
  ["Daily Workflow", "/daily-workflow", "☀"],
  ["Categories", "/settings/categories", "◇"],
  ["Settings", "/settings", "⚙"],
  ["Reports", "/reports", "▥"]
] as const;

interface SidebarProps {
  closeButtonRef: RefObject<HTMLButtonElement | null>;
  isMobile: boolean;
  isOpen: boolean;
  onClose: (restoreFocus?: boolean) => void;
}

export function Sidebar({ closeButtonRef, isMobile, isOpen, onClose }: SidebarProps) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    onClose(false);
    navigate("/login", { replace: true });
  }

  return (
    <aside
      className={isOpen ? "sidebar sidebar--open" : "sidebar"}
      id="application-sidebar"
      aria-label="Navegación principal"
      {...(isMobile && !isOpen ? { inert: true } : {})}
    >
      <div className="sidebar__header">
        <NavLink className="brand" to="/dashboard" onClick={isMobile ? () => onClose() : undefined}>
          <span className="brand__mark" aria-hidden="true">L</span>
          <span>LifeManager</span>
        </NavLink>
        <button
          ref={closeButtonRef}
          className="sidebar__close"
          type="button"
          aria-label="Cerrar menú de navegación"
          onClick={() => onClose()}
        >
          ×
        </button>
      </div>
      <nav className="sidebar__nav" aria-label="Secciones de LifeManager">
        {navigation.map(([label, path, icon]) => (
          <NavLink
            className={({ isActive }) =>
              isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
            }
            key={path}
            to={path}
            end
            onClick={isMobile ? () => onClose() : undefined}
          >
            <span className="sidebar__icon" aria-hidden="true">{icon}</span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__footer">
        <button className="sidebar__logout" type="button" onClick={handleLogout}>
          <span aria-hidden="true">↪</span>
          <span>Cerrar sesión</span>
        </button>
      </div>
    </aside>
  );
}
