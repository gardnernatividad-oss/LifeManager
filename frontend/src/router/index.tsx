import { createBrowserRouter, Navigate } from "react-router-dom";

import { AuthenticatedLayout } from "../layouts/AuthenticatedLayout";
import { PublicLayout } from "../layouts/PublicLayout";
import { PagePlaceholder } from "../components/common/PagePlaceholder";
import { LoginPage } from "../pages/auth/LoginPage";
import { RegistrationPage } from "../pages/auth/RegistrationPage";
import { ConfigurationPage } from "../pages/configuration/ConfigurationPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { HomePage } from "../pages/home/HomePage";
import { ReviewPage } from "../pages/review/ReviewPage";
import { PlanningTasksPage } from "../pages/planning/PlanningTasksPage";
import { PlanningPendingItemsPage } from "../pages/planning/PlanningPendingItemsPage";
import { PlanningProjectsPage } from "../pages/planning/PlanningProjectsPage";
import { CategoriesTablePage } from "../pages/tables/CategoriesTablePage";
import { MasterTasksTablePage } from "../pages/tables/MasterTasksTablePage";
import { ActivityMastersTablePage } from "../pages/tables/ActivityMastersTablePage";
import { TrackingTasksPage } from "../pages/tracking/TrackingTasksPage";
import { TrackingPendingItemsPage } from "../pages/tracking/TrackingPendingItemsPage";
import { TrackingProjectsPage } from "../pages/tracking/TrackingProjectsPage";
import { TaskReportsPage } from "../pages/reports/TaskReportsPage";
import { PendingItemReportsPage } from "../pages/reports/PendingItemReportsPage";
import { ProjectReportsPage } from "../pages/reports/ProjectReportsPage";
import { ProtectedRoute, PublicOnlyRoute } from "./RouteGuards";

const placeholder = (title: string) => (
  <PagePlaceholder
    title={title}
    description="Este módulo se está reconstruyendo para LifeManager V1."
  />
);

export const v1PlaceholderRoutes: ReadonlyArray<readonly [string, string]> = [];

export const appRouter = createBrowserRouter([
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/registro", element: <RegistrationPage /> }
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
          { path: "/planificacion/proyectos", element: <PlanningProjectsPage /> },
          { path: "/tablas/tareas", element: <MasterTasksTablePage /> },
          { path: "/tablas/categorias", element: <CategoriesTablePage /> },
          { path: "/tablas/actividades", element: <ActivityMastersTablePage /> },
          { path: "/seguimiento/tareas", element: <TrackingTasksPage /> },
          { path: "/seguimiento/pendientes", element: <TrackingPendingItemsPage /> },
          { path: "/seguimiento/proyectos", element: <TrackingProjectsPage /> },
          { path: "/reportes/tareas", element: <TaskReportsPage /> },
          { path: "/reportes/pendientes", element: <PendingItemReportsPage /> },
          { path: "/reportes/proyectos", element: <ProjectReportsPage /> },
          { path: "/configuracion", element: <ConfigurationPage /> },
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
