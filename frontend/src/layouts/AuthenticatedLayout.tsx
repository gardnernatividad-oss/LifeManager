import { Outlet } from "react-router-dom";

import { Sidebar } from "../components/layout/Sidebar";
import { Topbar } from "../components/layout/Topbar";

export function AuthenticatedLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-layout__main">
        <Topbar />
        <main className="content-container">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
