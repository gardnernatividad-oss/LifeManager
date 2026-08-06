import { Outlet } from "react-router-dom";

export function PublicLayout() {
  return (
    <main className="public-layout">
      <div className="public-layout__content">
        <Outlet />
      </div>
    </main>
  );
}
