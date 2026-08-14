import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { HomePage } from "../pages/home/HomePage";
import { ReviewPage } from "../pages/review/ReviewPage";
import { PlanningTasksPage } from "../pages/planning/PlanningTasksPage";
import { PlanningPendingItemsPage } from "../pages/planning/PlanningPendingItemsPage";
import { PlanningProjectsPage } from "../pages/planning/PlanningProjectsPage";
import { appRouter, v1PlaceholderRoutes } from "./index";

describe("V1 route contract", () => {
  it("registers every finalized protected route", () => {
    expect(["/inicio", "/revision", "/planificacion/tareas", "/planificacion/pendientes", "/planificacion/proyectos", ...v1PlaceholderRoutes.map(([path]) => path)]).toEqual([
      "/inicio",
      "/revision",
      "/planificacion/tareas",
      "/planificacion/pendientes",
      "/planificacion/proyectos",
      "/seguimiento/tareas",
      "/seguimiento/pendientes",
      "/seguimiento/proyectos",
      "/reportes/tareas",
      "/reportes/pendientes",
      "/reportes/proyectos",
      "/tablas/tareas",
      "/tablas/categorias",
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
