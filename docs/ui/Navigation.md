# Navegación de LifeManager

## V1 actual

El runtime V1.0.0 expone Inicio, Revisión, Planificación, Seguimiento, Reportes, Tablas y Configuración dentro de un único Personal Workspace implícito. Las rutas exactas se conservan en el router frontend y en `docs/requirements/Functional.md`.

## Objetivo V2 aprobado

La navegación mantiene las áreas principales y añade Calendario/Actividades y capacidades colaborativas. El detalle exacto de rutas se definirá con los contratos frontend V2.

### Vistas globales

- Inicio.
- Revisión.
- Mi calendario.

Estas vistas agregan información entre Workspaces y no muestran el selector global de Workspace.

### Vistas dependientes de Workspace

- Planificación: Tareas, Pendientes y Proyectos.
- Seguimiento: Tareas, Pendientes y Proyectos.
- Reportes, cuando el análisis pertenece a un Workspace.
- Tablas: Tareas, Actividades y Categorías.
- Administración pertinente de miembros/Workspace dentro de Configuración.

Mi calendario usa sus propios controles internos para colaboración y comparación.

## Detalles y overlays

- `>` abre una página interna en el área blanca con flecha de retorno.
- No se expanden detalles debajo de una fila.
- `+ Nueva` abre normalmente un modal compacto para entidades simples.
- El centro de notificaciones es un panel/modal/overlay, no una página.
- Recordatorio diario abre Inicio; Revisión diaria abre Revisión; los recordatorios de Seguimiento abren Pendientes o Proyectos; un recordatorio de Actividad abre su contexto de Calendario/Actividad.
- Configuración no incorpora una segunda barra lateral permanente.

La terminología visible usa Etapa, Propietario, Miembro, Líder, Responsable, Organizador y Participantes; no presenta nombres internos del código.
