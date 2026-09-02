import type { RefObject } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { appNavigation, type NavigationSection } from "../../router/navigation";

interface SidebarProps {
  closeButtonRef: RefObject<HTMLButtonElement | null>;
  isMobile: boolean;
  isOpen: boolean;
  onClose: (restoreFocus?: boolean) => void;
}

export function Sidebar({ closeButtonRef, isMobile, isOpen, onClose }: SidebarProps) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  async function handleLogout() {
    await logout();
    onClose(false);
    navigate("/login", { replace: true });
  }

  function link(section: NavigationSection) {
    if (!section.path) return null;
    return (
      <NavLink
        className={({ isActive }) =>
          isActive ? "sidebar__link sidebar__link--active" : "sidebar__link"
        }
        to={section.path}
        end
        onClick={isMobile ? () => onClose() : undefined}
      >
        <span className="sidebar__icon" aria-hidden="true">{section.icon}</span>
        <span>{section.label}</span>
      </NavLink>
    );
  }

  return (
    <aside
      className={isOpen ? "sidebar sidebar--open" : "sidebar"}
      id="application-sidebar"
      aria-label="Navegación principal"
      {...(isMobile && !isOpen ? { inert: true } : {})}
    >
      <div className="sidebar__header">
        <NavLink className="brand" to="/inicio" onClick={isMobile ? () => onClose() : undefined}>
          <span className="brand__mark" aria-hidden="true">L</span>
          <span>LifeManager</span>
        </NavLink>
        <button ref={closeButtonRef} className="sidebar__close" type="button" aria-label="Cerrar menú de navegación" onClick={() => onClose()}>×</button>
      </div>
      <nav className="sidebar__nav" aria-label="Secciones de LifeManager">
        {appNavigation.filter((section) => !section.globalAdminOnly || user?.global_role === "GLOBAL_ADMIN").map((section) => section.children ? (
          <details className="sidebar__group" key={section.label} open={section.children.some((child) => location.pathname === child.path)}>
            <summary className="sidebar__group-label">
              <span className="sidebar__icon" aria-hidden="true">{section.icon}</span>
              <span>{section.label}</span>
            </summary>
            <div className="sidebar__subnav">
              {section.children.map((child) => (
                <NavLink
                  className={({ isActive }) => isActive ? "sidebar__sublink sidebar__sublink--active" : "sidebar__sublink"}
                  key={child.path}
                  to={child.path}
                  end
                  onClick={isMobile ? () => onClose() : undefined}
                >{child.label}</NavLink>
              ))}
            </div>
          </details>
        ) : <div key={section.label}>{link(section)}</div>)}
      </nav>
      <div className="sidebar__footer">
        <button className="sidebar__logout" type="button" onClick={() => void handleLogout()}>
          <span aria-hidden="true">↪</span><span>Cerrar sesión</span>
        </button>
      </div>
    </aside>
  );
}
