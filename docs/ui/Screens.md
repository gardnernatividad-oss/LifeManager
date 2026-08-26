# Inventario de pantallas de LifeManager

## Gestión de Workspaces

Configuración separa Workspaces activos e inactivos e integra creación Shared,
invitaciones, miembros, transferencia, salida/retiro, resolución de
responsabilidades, desactivación, reactivación y eliminación elegible. Las
acciones dependen de `visible_role`, lifecycle y `can_delete` calculados por el
backend.

## V1 actual

Las pantallas implementadas son Login, Registro, Inicio, Revisión, Planificación/Seguimiento/Reportes de Tareas, Pendientes y Proyectos, Tablas de Tareas/Categorías y Configuración. El frontend actual opera sobre el Personal Workspace implícito.

## Objetivo V2 aprobado

| Alcance | Pantalla | Propósito |
|---|---|---|
| Global | Inicio | Resumen conciso del día entre Workspaces. |
| Global | Revisión | Guardado independiente de Tareas, Pendientes y Etapas asignadas. |
| Global | Mi calendario | Actividades del usuario entre todos los Workspaces. |
| Workspace | Planificación · Tareas | Crear Tareas puntuales o recurrencias finitas; filtrar por fecha, Responsable, catálogo, Categoría, estado derivado y origen; editar/eliminar futuras con `Solo esta`/`Todas las futuras` cuando son generadas; resolver Pendientes sin reprogramarlas. Desktop usa tabla compacta y móvil tarjetas legibles. |

Stage 5.4 cierra el gate de esta pantalla: las acciones visibles proceden de
capacidades server-side, el cambio de Workspace limpia estado privado y no hay
overflow horizontal en la representación móvil.
| Workspace | Planificación · Pendientes | Crear, asignar y mantener planificación. |
| Workspace | Planificación · Proyectos | Mantener Proyecto, Líder y Etapas. |
| Workspace | Seguimiento · Tareas | Registro y correcciones aprobadas. |
| Workspace | Seguimiento · Pendientes | Avance, comentario e historia. |
| Workspace | Seguimiento · Proyectos | Avance e historia de Proyecto/Etapas. |
| Workspace | Reportes | Periodo, Responsable y Categoría; métricas por refinar. |
| Workspace | Tablas · Tareas | Catálogo visible como Tareas. |
| Workspace | Tablas · Actividades | Catálogo de Actividades Activas/Inactivas. |
| Workspace | Tablas · Categorías | Clasificación reutilizable. |
| Workspace | Tablas · gestión | Buscar, filtrar por vigencia, crear, editar, activar y desactivar Categorías, Tareas y Actividades sin exponer nombres técnicos. |
| Workspace | Tablas · ciclo seguro | Eliminar solo cuando `can_delete` viene habilitado por backend; en caso contrario, desactivar. La reclasificación dinámica se advierte antes de guardar. |
| Workspace | Tablas · gate 4.3 | Gestión responsive y accesible, aislada por Workspace y cerrada para Categorías, Tareas y Actividades; las ocurrencias siguen pendientes. |
| Cuenta/Workspace | Configuración | Perfil, recordatorios, membresías, privacidad, seguridad y versión. |
| Overlay | Notificaciones | Membresía, asignaciones, Actividades y recordatorios relevantes; no incluye comentarios ni es página completa. |

## Detalles internos

- Pendiente: vista general → `>` → detalle con historia.
- Proyecto: vista general → `>` → detalle y lista de Etapas.
- Etapa: lista dentro del Proyecto → `>` → detalle e historia.
- Comparación de Calendario: página interna diaria separada.

Móvil usa composición vertical compacta y mueve información secundaria a detalles. Desktop puede mostrar tablas más ricas sin convertir el scroll horizontal en la estrategia móvil principal.
