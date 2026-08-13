import { describe, expect, it } from "vitest";

import { v1PlaceholderRoutes } from "./index";

describe("V1 route contract", () => {
  it("registers every finalized protected route", () => {
    expect(v1PlaceholderRoutes.map(([path]) => path)).toEqual([
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
