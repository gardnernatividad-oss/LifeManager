export interface NavigationSection {
  label: string;
  icon: string;
  path?: string;
  children?: readonly { label: string; path: string }[];
}

export const appNavigation: readonly NavigationSection[] = [
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
