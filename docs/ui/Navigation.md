# Navegación de LifeManager

## Integración de Workspace implementada

El selector usa el listado operacional autenticado, muestra Personal primero
y valida cualquier UUID preferido antes de reutilizarlo. Aparece en
Planificación, Seguimiento, Tablas, Reportes y gestión de Configuración. No se
muestra en Inicio, Revisión ni Mi calendario. Cambiar de Workspace invalida
cachés scoped y nunca concede autorización.

## V1 actual

El runtime V1.0.0 expone Inicio, Revisión, Planificación, Seguimiento, Reportes, Tablas y Configuración dentro de un único Personal Workspace implícito. Las rutas exactas se conservan en el router frontend y en `docs/requirements/Functional.md`.

## Objetivo V2 aprobado

La navegación mantiene las áreas principales y añade Calendario/Actividades y capacidades colaborativas. Las rutas siguen el modelo aprobado en `docs/architecture/V2-Architecture-Baseline.md`: vistas globales fuera de scope y vistas dependientes bajo `/w/:workspaceId/...`.

### Vistas globales

- Inicio.
- Revisión.
- Mi calendario.

Estas vistas agregan información entre Workspaces y no muestran el selector global de Workspace.

### Vistas dependientes de Workspace

- Planificación: Tareas, Pendientes y Proyectos.

`Planificación → Tareas` usa el Workspace seleccionado y permite elegir entre
una ocurrencia puntual o una repetición finita diaria, semanal o mensual. Las
ocurrencias generadas aparecen como Tareas normales. Una futura generada ofrece
`Solo esta` y `Todas las futuras`; las independientes se editan directamente.
No debe confundirse con `Tablas → Tareas`, que
administra el catálogo reutilizable.
Stage 5.4 confirma que el cambio de Workspace reinicia formularios, filtros y
diálogos de alcance de esta pantalla; las query keys incluyen `workspace_id` y
logout limpia la caché privada.
`Planificación → Pendientes` presenta filtros combinables y paginación sobre
consultas aisladas por Workspace. En desktop usa tarjetas horizontales con el
resumen operativo completo; en pantallas estrechas las convierte en tarjetas
verticales sin desplazamiento horizontal. Diferencia el registro inicialmente
vacío de una búsqueda sin coincidencias.
`Planificación → Pendientes → >` abre una pantalla interna con flecha de
retorno, resumen mobile-first, seguimiento inline e historial en tarjetas. El
historial muestra fecha/hora, actor, avance, etiqueta Seguimiento/Corrección y
comentario escapado. Las query keys incluyen Workspace y Pending; cambiar de
Workspace desmonta el detalle y limpia comentarios no enviados.

- Seguimiento: Tareas, Pendientes y Proyectos.
- Reportes, cuando el análisis pertenece a un Workspace.
- Tablas: Tareas, Actividades y Categorías.

Stage 4.1 habilita estas tres vistas sobre el Workspace seleccionado. El cambio de Workspace cambia también sus consultas y cachés; no existe un catálogo global.

Los selectores reutilizables de Stage 4.2 también están aislados por Workspace. Para nuevas selecciones muestran únicamente opciones Activas; un formulario de edición puede pedir explícitamente su valor inactivo actual.

Stage 4.3 cierra el gate de estas vistas y confirma que Categorías, Tareas y
Actividades comparten lifecycle, autorización, aislamiento de caché y patrones
responsive/accesibles coherentes.
- Administración pertinente de miembros/Workspace dentro de Configuración.

Mi calendario usa sus propios controles internos para colaboración y comparación.

### Patrones de ruta

- globales: `/inicio`, `/revision`, `/calendario`, `/configuracion/*`, `/administracion/*`;
- Workspace: `/w/:workspaceId/tareas`, `/pendientes`, `/proyectos`, `/tablas/*`, `/reportes/*` y `/calendario/*` bajo ese prefijo;
- detalle: Pendiente, Proyecto y Etapa incorporan sus UUID en rutas anidadas;
- autenticación preserva un destino interno seguro y valida nuevamente sesión/membership al restaurar.

## Detalles y overlays

- `>` abre una página interna en el área blanca con flecha de retorno.
- No se expanden detalles debajo de una fila.
- `+ Nueva` abre normalmente un modal compacto para entidades simples.
- El centro de notificaciones es un panel/modal/overlay, no una página.
- Recordatorio diario abre Inicio; Revisión diaria abre Revisión; los recordatorios de Seguimiento abren Pendientes o Proyectos; un recordatorio de Actividad abre su contexto de Calendario/Actividad.
- Configuración no incorpora una segunda barra lateral permanente.

La terminología visible usa Etapa, Propietario, Miembro, Líder, Responsable, Organizador y Participantes; no presenta nombres internos del código.
