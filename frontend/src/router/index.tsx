import { createBrowserRouter, Navigate } from "react-router-dom";

import { AuthenticatedLayout } from "../layouts/AuthenticatedLayout";
import { PublicLayout } from "../layouts/PublicLayout";
import { DailyWorkflowPage } from "../pages/daily-workflow/DailyWorkflowPage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { LoginPage } from "../pages/auth/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { ProjectsPage } from "../pages/projects/ProjectsPage";
import { ReportsPage } from "../pages/reports/ReportsPage";
import { CategoriesPage } from "../pages/settings/CategoriesPage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { RecurringTasksPage } from "../pages/tasks/RecurringTasksPage";
import { TasksPage } from "../pages/tasks/TasksPage";
import { ProtectedRoute, PublicOnlyRoute } from "./RouteGuards";

export const appRouter = createBrowserRouter([
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        element: <PublicLayout />,
        children: [{ path: "/login", element: <LoginPage /> }]
      }
    ]
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AuthenticatedLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "/dashboard", element: <DashboardPage /> },
          { path: "/tasks", element: <TasksPage /> },
          { path: "/tasks/recurring", element: <RecurringTasksPage /> },
          { path: "/projects", element: <ProjectsPage /> },
          { path: "/daily-workflow", element: <DailyWorkflowPage /> },
          { path: "/settings/categories", element: <CategoriesPage /> },
          { path: "/settings", element: <SettingsPage /> },
          { path: "/reports", element: <ReportsPage /> }
        ]
      }
    ]
  },
  { path: "*", element: <NotFoundPage /> }
]);
