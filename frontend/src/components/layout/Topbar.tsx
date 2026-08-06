import { useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

export function Topbar() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="topbar">
      <span>Workspace</span>
      <div className="topbar__session">
        <span className="topbar__user">{user?.first_name ?? user?.email}</span>
        <button className="text-button" type="button" onClick={handleLogout}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
