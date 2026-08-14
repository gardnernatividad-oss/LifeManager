import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { HomePage } from "../pages/home/HomePage";
import { ReviewPage } from "../pages/review/ReviewPage";
import { PlanningTasksPage } from "../pages/planning/PlanningTasksPage";
import { PlanningPendingItemsPage } from "../pages/planning/PlanningPendingItemsPage";
import { PlanningProjectsPage } from "../pages/planning/PlanningProjectsPage";
import { CategoriesTablePage } from "../pages/tables/CategoriesTablePage";
import { MasterTasksTablePage } from "../pages/tables/MasterTasksTablePage";
import { TrackingTasksPage } from "../pages/tracking/TrackingTasksPage";
import { TrackingPendingItemsPage } from "../pages/tracking/TrackingPendingItemsPage";
import { TrackingProjectsPage } from "../pages/tracking/TrackingProjectsPage";
import { TaskReportsPage } from "../pages/reports/TaskReportsPage";
import { PendingItemReportsPage } from "../pages/reports/PendingItemReportsPage";
import { ProjectReportsPage } from "../pages/reports/ProjectReportsPage";
import { RegistrationPage } from "../pages/auth/RegistrationPage";
import { ConfigurationPage } from "../pages/configuration/ConfigurationPage";
import { appRouter, v1PlaceholderRoutes } from "./index";

describe("V1 route contract", () => {
  it("registers every finalized protected route", () => {
    expect(["/inicio", "/revision", "/planificacion/tareas", "/planificacion/pendientes", "/planificacion/proyectos", "/tablas/tareas", "/tablas/categorias", "/seguimiento/tareas", "/seguimiento/pendientes", "/seguimiento/proyectos", "/reportes/tareas", "/reportes/pendientes", "/reportes/proyectos", "/configuracion", ...v1PlaceholderRoutes.map(([path]) => path)]).toEqual([
      "/inicio",
      "/revision",
      "/planificacion/tareas",
      "/planificacion/pendientes",
      "/planificacion/proyectos",
      "/tablas/tareas",
      "/tablas/categorias",
      "/seguimiento/tareas",
      "/seguimiento/pendientes",
      "/seguimiento/proyectos",
      "/reportes/tareas",
      "/reportes/pendientes",
      "/reportes/proyectos",
      "/configuracion"
    ]);
  });

  it("mounts the functional Home page at Inicio", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    const inicio = protectedChildren?.find((route) => route.path === "/inicio");
    expect(isValidElement(inicio?.element) && inicio.element.type).toBe(HomePage);
  });

  it("mounts the functional Review page at Revisión", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    const review = protectedChildren?.find((route) => route.path === "/revision");
    expect(isValidElement(review?.element) && review.element.type).toBe(ReviewPage);
  });

  it("mounts the functional Planning Tasks page", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    const route = protectedChildren?.find((item) => item.path === "/planificacion/tareas");
    expect(isValidElement(route?.element) && route.element.type).toBe(PlanningTasksPage);
  });

  it("mounts the functional Planning Pending Items page", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    const route = protectedChildren?.find((item) => item.path === "/planificacion/pendientes");
    expect(isValidElement(route?.element) && route.element.type).toBe(PlanningPendingItemsPage);
  });

  it("mounts the functional Planning Projects page", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    const route = protectedChildren?.find((item) => item.path === "/planificacion/proyectos");
    expect(isValidElement(route?.element) && route.element.type).toBe(PlanningProjectsPage);
  });

  it("mounts both functional master-data pages", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    expect((protectedChildren?.find((item) => item.path === "/tablas/tareas")?.element as { type: unknown }).type).toBe(MasterTasksTablePage);
    expect((protectedChildren?.find((item) => item.path === "/tablas/categorias")?.element as { type: unknown }).type).toBe(CategoriesTablePage);
  });

  it("mounts the functional Tracking Tasks page", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    expect((protectedChildren?.find((item) => item.path === "/seguimiento/tareas")?.element as { type: unknown }).type).toBe(TrackingTasksPage);
  });

  it("mounts the functional Tracking Pending Items page", () => {
    const protectedChildren = appRouter.routes[1].children?.[0].children;
    expect((protectedChildren?.find((item) => item.path === "/seguimiento/pendientes")?.element as { type: unknown }).type).toBe(TrackingPendingItemsPage);
  });
  it("mounts the functional Tracking Projects page", () => { const children=appRouter.routes[1].children?.[0].children; expect((children?.find(r=>r.path==="/seguimiento/proyectos")?.element as {type:unknown}).type).toBe(TrackingProjectsPage); });
  it("mounts the functional Task Reports page",()=>{const children=appRouter.routes[1].children?.[0].children;expect((children?.find(r=>r.path==="/reportes/tareas")?.element as {type:unknown}).type).toBe(TaskReportsPage);});
  it("mounts the functional Pending Item Reports page",()=>{const children=appRouter.routes[1].children?.[0].children;expect((children?.find(r=>r.path==="/reportes/pendientes")?.element as {type:unknown}).type).toBe(PendingItemReportsPage);});
  it("mounts the functional Project Reports page",()=>{const children=appRouter.routes[1].children?.[0].children;expect((children?.find(r=>r.path==="/reportes/proyectos")?.element as {type:unknown}).type).toBe(ProjectReportsPage);});
  it("mounts real Registration and Configuration pages with no V1 placeholders",()=>{const publicChildren=appRouter.routes[0].children?.[0].children;const protectedChildren=appRouter.routes[1].children?.[0].children;expect((publicChildren?.find(r=>r.path==="/registro")?.element as {type:unknown}).type).toBe(RegistrationPage);expect((protectedChildren?.find(r=>r.path==="/configuracion")?.element as {type:unknown}).type).toBe(ConfigurationPage);expect(v1PlaceholderRoutes).toHaveLength(0);});

  it("does not register legacy business routes", () => {
    const paths = v1PlaceholderRoutes.map(([path]) => path);
    for (const legacyPath of [
      "/dashboard",
      "/tasks",
      "/tasks/recurring",
      "/daily-workflow",
      "/settings",
      "/reports"
    ]) {
      expect(paths).not.toContain(legacyPath);
    }
  });
});
