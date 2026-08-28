export interface NavigationSection {
  label: string;
  icon: string;
  path?: string;
  children?: readonly { label: string; path: string }[];
}

export const v1Navigation: readonly NavigationSection[] = [
  { label: "Inicio", path: "/inicio", icon: "⌂" },
  { label: "Revisión", path: "/revision", icon: "✓" },
  { label: "Mi calendario", path: "/calendario", icon: "▦" },
  {
    label: "Planificación",
    icon: "＋",
    children: [
      { label: "Tareas", path: "/planificacion/tareas" },
      { label: "Pendientes", path: "/planificacion/pendientes" },
      { label: "Proyectos", path: "/planificacion/proyectos" },
      { label: "Actividades", path: "/planificacion/actividades" }
    ]
  },
  {
    label: "Seguimiento",
    icon: "◎",
    children: [
      { label: "Tareas", path: "/seguimiento/tareas" },
      { label: "Pendientes", path: "/seguimiento/pendientes" },
      { label: "Proyectos", path: "/seguimiento/proyectos" }
    ]
  },
  {
    label: "Reportes",
    icon: "▥",
    children: [
      { label: "Tareas", path: "/reportes/tareas" },
      { label: "Pendientes", path: "/reportes/pendientes" },
      { label: "Proyectos", path: "/reportes/proyectos" }
    ]
  },
  {
    label: "Tablas",
    icon: "▦",
    children: [
      { label: "Tareas", path: "/tablas/tareas" },
      { label: "Actividades", path: "/tablas/actividades" },
      { label: "Categorías", path: "/tablas/categorias" }
    ]
  },
  { label: "Configuración", path: "/configuracion", icon: "⚙" }
] as const;
