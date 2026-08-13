import { createBrowserRouter, Navigate } from "react-router-dom";

import { AuthenticatedLayout } from "../layouts/AuthenticatedLayout";
import { PublicLayout } from "../layouts/PublicLayout";
import { PagePlaceholder } from "../components/common/PagePlaceholder";
import { LoginPage } from "../pages/auth/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { HomePage } from "../pages/home/HomePage";
import { ReviewPage } from "../pages/review/ReviewPage";
import { PlanningTasksPage } from "../pages/planning/PlanningTasksPage";
import { PlanningPendingItemsPage } from "../pages/planning/PlanningPendingItemsPage";
import { ProtectedRoute, PublicOnlyRoute } from "./RouteGuards";

const placeholder = (title: string) => (
  <PagePlaceholder
    title={title}
    description="Este módulo se está reconstruyendo para LifeManager V1."
  />
);

export const v1PlaceholderRoutes = [
  ["/planificacion/proyectos", "Planificación · Proyectos"],
  ["/seguimiento/tareas", "Seguimiento · Tareas"],
  ["/seguimiento/pendientes", "Seguimiento · Pendientes"],
  ["/seguimiento/proyectos", "Seguimiento · Proyectos"],
  ["/reportes/tareas", "Reportes · Tareas"],
  ["/reportes/pendientes", "Reportes · Pendientes"],
  ["/reportes/proyectos", "Reportes · Proyectos"],
  ["/tablas/tareas", "Tablas · Tareas"],
  ["/tablas/categorias", "Tablas · Categorías"],
  ["/configuracion", "Configuración"]
] as const;

export const appRouter = createBrowserRouter([
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/registro", element: placeholder("Registro") }
        ]
      }
    ]
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AuthenticatedLayout />,
        children: [
          { index: true, element: <Navigate to="/inicio" replace /> },
          { path: "/inicio", element: <HomePage /> },
          { path: "/revision", element: <ReviewPage /> },
          { path: "/planificacion/tareas", element: <PlanningTasksPage /> },
          { path: "/planificacion/pendientes", element: <PlanningPendingItemsPage /> },
          ...v1PlaceholderRoutes.map(([path, title]) => ({
            path,
            element: placeholder(title)
          }))
        ]
      }
    ]
  },
  { path: "*", element: <NotFoundPage /> }
]);
