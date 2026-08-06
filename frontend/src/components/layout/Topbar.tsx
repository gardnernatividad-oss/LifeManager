import type { RefObject } from "react";

import { useAuth } from "../../hooks/useAuth";

interface TopbarProps {
  isMenuOpen: boolean;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
  onMenuToggle: () => void;
}

export function Topbar({ isMenuOpen, menuButtonRef, onMenuToggle }: TopbarProps) {
  const { user } = useAuth();
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ");

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
          <span className="topbar__label">Espacio de trabajo</span>
          <strong>Personal</strong>
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
