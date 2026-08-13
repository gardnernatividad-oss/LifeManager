import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

function AuthenticationLoading() {
  return (
    <main className="auth-loading" aria-live="polite">
      <span className="loading-spinner" aria-hidden="true" />
      <span>Comprobando sesión…</span>
    </main>
  );
}

export function ProtectedRoute() {
  const { isAuthenticated, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <AuthenticationLoading />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { isAuthenticated, isInitializing } = useAuth();

  if (isInitializing) {
    return <AuthenticationLoading />;
  }

  if (isAuthenticated) {
    return <Navigate to="/inicio" replace />;
  }

  return <Outlet />;
}
