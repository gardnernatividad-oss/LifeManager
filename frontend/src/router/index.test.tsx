import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { RegistrationPage } from "../pages/auth/RegistrationPage";
import { ConfigurationPage } from "../pages/configuration/ConfigurationPage";
import { HomePage } from "../pages/home/HomePage";
import { PlanningPendingItemsPage } from "../pages/planning/PlanningPendingItemsPage";
import { PlanningProjectsPage } from "../pages/planning/PlanningProjectsPage";
import { PlanningTasksPage } from "../pages/planning/PlanningTasksPage";
import { ReviewPage } from "../pages/review/ReviewPage";
import { ReportsPage } from "../pages/reports/ReportsPage";
import { CategoriesTablePage } from "../pages/tables/CategoriesTablePage";
import { MasterTasksTablePage } from "../pages/tables/MasterTasksTablePage";
import { appRouter, v1PlaceholderRoutes } from "./index";

const protectedChildren = appRouter.routes[1].children?.[0].children;
const route = (path: string) => protectedChildren?.find((item) => item.path === path);
const elementType = (path: string) => {
  const element = route(path)?.element;
  return isValidElement(element) ? element.type : null;
};

describe("V2 route contract", () => {
  it("mounts the active V2 Home, Review, Planning and master-data pages", () => {
    expect(elementType("/inicio")).toBe(HomePage);
    expect(elementType("/revision")).toBe(ReviewPage);
    expect(elementType("/planificacion/tareas")).toBe(PlanningTasksPage);
    expect(elementType("/planificacion/pendientes")).toBe(PlanningPendingItemsPage);
    expect(elementType("/planificacion/proyectos")).toBe(PlanningProjectsPage);
    expect(elementType("/reportes")).toBe(ReportsPage);
    expect((route("/tablas/tareas")?.element as { type: unknown }).type).toBe(MasterTasksTablePage);
    expect((route("/tablas/categorias")?.element as { type: unknown }).type).toBe(CategoriesTablePage);
  });

  it("does not expose V1 Tracking or legacy nested Reports clients as active V2 routes", () => {
    const paths = protectedChildren?.map((item) => item.path).filter(Boolean) ?? [];
    expect(paths.some((path) => path?.startsWith("/seguimiento/"))).toBe(false);
    expect(paths.some((path) => path?.startsWith("/reportes/"))).toBe(false);
  });

  it("keeps real Registration and Configuration pages with no placeholders", () => {
    const publicChildren = appRouter.routes[0].children?.[0].children;
    expect((publicChildren?.find((item) => item.path === "/registro")?.element as { type: unknown }).type).toBe(RegistrationPage);
    expect((route("/configuracion")?.element as { type: unknown }).type).toBe(ConfigurationPage);
    expect(v1PlaceholderRoutes).toHaveLength(0);
  });

  it("does not register former legacy shell routes", () => {
    const paths = protectedChildren?.map((item) => item.path).filter(Boolean) ?? [];
    for (const legacyPath of ["/dashboard", "/tasks", "/tasks/recurring", "/daily-workflow", "/settings", "/reports"]) {
      expect(paths).not.toContain(legacyPath);
    }
  });
});
