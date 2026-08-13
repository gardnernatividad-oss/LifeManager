import { isValidElement } from "react";
import { describe, expect, it } from "vitest";

import { HomePage } from "../pages/home/HomePage";
import { appRouter, v1PlaceholderRoutes } from "./index";

describe("V1 route contract", () => {
  it("registers every finalized protected route", () => {
    expect(["/inicio", ...v1PlaceholderRoutes.map(([path]) => path)]).toEqual([
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
