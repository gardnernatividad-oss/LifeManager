import { useEffect, useRef, useState } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "../components/layout/Sidebar";
import { Topbar } from "../components/layout/Topbar";

export function AuthenticatedLayout() {
  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 48rem)");
    const updateViewport = () => {
      setIsMobile(mediaQuery.matches);
      if (!mediaQuery.matches) setIsSidebarOpen(false);
    };

    updateViewport();
    mediaQuery.addEventListener("change", updateViewport);
    return () => mediaQuery.removeEventListener("change", updateViewport);
  }, []);

  useEffect(() => {
    if (!isMobile || !isSidebarOpen) return;

    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSidebarOpen(false);
        menuButtonRef.current?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isMobile, isSidebarOpen]);

  function closeSidebar(restoreFocus = true) {
    setIsSidebarOpen(false);
    if (restoreFocus) menuButtonRef.current?.focus();
  }

  return (
    <div className="app-layout">
      <Sidebar
        closeButtonRef={closeButtonRef}
        isMobile={isMobile}
        isOpen={!isMobile || isSidebarOpen}
        onClose={closeSidebar}
      />
      {isMobile && isSidebarOpen ? (
        <button
          className="sidebar-overlay"
          type="button"
          aria-label="Cerrar menú de navegación"
          onClick={() => closeSidebar()}
        />
      ) : null}
      <div className="app-layout__main">
        <Topbar
          isMenuOpen={isSidebarOpen}
          menuButtonRef={menuButtonRef}
          onMenuToggle={isSidebarOpen ? () => closeSidebar() : () => setIsSidebarOpen(true)}
        />
        <main className="content-container" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
