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
import { PendingItemDetailPage } from "../pages/planning/PendingItemDetailPage";
import { PlanningProjectsPage } from "../pages/planning/PlanningProjectsPage";
import { PlanningActivitiesPage } from "../pages/planning/PlanningActivitiesPage";
import { MyCalendarPage } from "../pages/calendar/MyCalendarPage";
import { CalendarComparisonPage } from "../pages/calendar/CalendarComparisonPage";
import { CategoriesTablePage } from "../pages/tables/CategoriesTablePage";
import { MasterTasksTablePage } from "../pages/tables/MasterTasksTablePage";
import { ActivityMastersTablePage } from "../pages/tables/ActivityMastersTablePage";
import { ReportsPage } from "../pages/reports/ReportsPage";
import { AdminPage } from "../pages/admin/AdminPage";
import { V2ProjectDetailPage } from "../pages/projects/V2ProjectDetailPage";
import { V2ProjectStageDetailPage } from "../pages/projects/V2ProjectStageDetailPage";
import { GlobalAdminRoute, ProtectedRoute, PublicOnlyRoute } from "./RouteGuards";

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
          { path: "/calendario", element: <MyCalendarPage /> },
          { path: "/calendario/comparar", element: <CalendarComparisonPage /> },
          { path: "/planificacion/tareas", element: <PlanningTasksPage /> },
          { path: "/planificacion/pendientes", element: <PlanningPendingItemsPage /> },
          { path: "/planificacion/pendientes/:pendingItemId", element: <PendingItemDetailPage /> },
          { path: "/planificacion/proyectos", element: <PlanningProjectsPage /> },
          { path: "/planificacion/actividades", element: <PlanningActivitiesPage /> },
          { path: "/planificacion/proyectos/:projectId", element: <V2ProjectDetailPage mode="planning" /> },
          { path: "/planificacion/proyectos/:projectId/etapas/:stageId", element: <V2ProjectStageDetailPage mode="planning" /> },
          { path: "/tablas/tareas", element: <MasterTasksTablePage /> },
          { path: "/tablas/categorias", element: <CategoriesTablePage /> },
          { path: "/tablas/actividades", element: <ActivityMastersTablePage /> },
          { path: "/reportes", element: <ReportsPage /> },
          { path: "/configuracion", element: <ConfigurationPage /> },
          {
            element: <GlobalAdminRoute />,
            children: [{ path: "/administracion", element: <AdminPage /> }]
          },
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
