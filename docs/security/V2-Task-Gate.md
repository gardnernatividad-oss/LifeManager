# Gate de Tareas V2 — Stage 5.4

## Resultado

Stage 5.4 queda **Completado** y Phase 5 — Tareas queda **cerrada**. El gate
integra autorización, ciclo de vida, recurrencia, alcances de ocurrencia,
aislamiento, concurrencia, PostgreSQL desechable y UX. No añade funcionalidad.

## Matriz de actores

`PLAN` agrupa crear puntual/recurrente, listar, detalle y editar/eliminar una
Tarea futura elegible. `RESOLVE` agrupa Completada y No realizada para una
Pendiente. Los recursos inexistentes o ajenos se ocultan con `404`.

| Actor | PLAN en Workspace ACTIVE | RESOLVE de Tarea propia | RESOLVE de Tarea ajena |
|---|---:|---:|---:|
| Anónimo | 401 | 401 | 401 |
| Owner Personal ACTIVE | Sí | Sí | No aplica |
| Owner Shared ACTIVE | Sí | Sí | 403 |
| Member Shared ACTIVE | Sí | Sí | 403 |
| Miembro ACTIVE no responsable | Sí | — | 403 |
| Membership LEFT/REMOVED | 404 | 404 | 404 |
| No miembro | 404 | 404 | 404 |
| Cuenta DISABLED | 401 | 401 | 401 |
| GLOBAL_ADMIN sin membership | 404 | 404 | 404 |

Ser owner no concede autoridad especial sobre Tareas. `GLOBAL_ADMIN` no omite
membership. El Responsable actual es la única persona que puede resolver.

| Operación | Owner Personal ACTIVE | Owner/Member Shared ACTIVE | ACTIVE no responsable | Sin acceso operativo |
|---|---:|---:|---:|---:|
| Crear puntual | Sí | Sí | Sí | 401/404 |
| Crear recurrencia | Sí | Sí | Sí | 401/404 |
| Listar / detalle | Sí | Sí | Sí | 401/404 |
| Editar independiente futura | Sí | Sí | Sí | 401/404 |
| Editar generada `THIS` | Sí | Sí | Sí | 401/404 |
| Editar generada `THIS_AND_FUTURE` | Sí | Sí | Sí | 401/404 |
| Eliminar independiente futura | Sí | Sí | Sí | 401/404 |
| Eliminar generada `THIS` | Sí | Sí | Sí | 401/404 |
| Eliminar generada `THIS_AND_FUTURE` | Sí | Sí | Sí | 401/404 |
| Completar / No realizar Pendiente propia | Sí | Sí | Sí | 401/404 |
| Completar / No realizar Pendiente ajena | No aplica | 403 | 403 | 401/404 |

## Matriz de ciclo y operaciones

| Tipo/estado | Editar THIS | Editar futuras | Eliminar THIS | Eliminar futuras | Resolver |
|---|---:|---:|---:|---:|---:|
| Independiente futura sin resultado | Sí | No | Sí | No | No |
| Independiente hoy/vencida sin resultado | No | No | No | No | Responsable |
| Generada futura sin resultado | Sí | Sí | Sí | Sí | No |
| Generada hoy/vencida sin resultado | No | No | No | No | Responsable |
| COMPLETED / NOT_COMPLETED | No | No | No | No | No |

`planned_date > fecha local` deriva Programada; `planned_date <= fecha local`
deriva Pendiente. Esos estados no se persisten. No existe Atrasada. Intentar
reprogramar una Pendiente, resolver anticipadamente una Programada o mutar una
resuelta produce conflicto antes del flush.

## Alcances y procedencia

- `THIS` afecta exclusivamente la ocurrencia futura seleccionada.
- `THIS_AND_FUTURE` toma la seleccionada y posteriores del mismo
  `GenerationBatch`, solo si siguen futuras y sin resultado.
- Anteriores, hoy, pasado y futuras resueltas se preservan.
- El conjunto se bloquea en orden `planned_date,id` y se refresca con
  `populate_existing=True` después de esperar el lock.
- El batch original no se modifica ni desaparece al eliminar ocurrencias y su
  UUID no se expone en `TaskRead`.

La regeneración del calendario al cambiar patrón, límites o anclas no está
implementada. Requerirá un contrato futuro explícito y nueva procedencia.

## Recurrencia e identidad

DAILY, WEEKLY y MONTHLY exigen límites inclusivos finitos. WEEKLY usa lunes=0
hasta domingo=6. MONTHLY acepta varias anclas; 29/30/31 usan el último día del
mes cuando corresponde y las colisiones se deduplican. Cada solicitud admite
como máximo 1000 ocurrencias y crea un batch atómico.

La identidad es Workspace + MasterTask + fecha + Responsable. La misma
combinación colisiona; dos responsables distintos pueden compartir MasterTask y
fecha. El master y Responsable deben estar activos y pertenecer al Workspace.
Las FK compuestas y restricciones PostgreSQL son la frontera final.

## Seguridad y contratos

- Toda ruta Task exige cuenta utilizable y membership activa del Workspace
  activo; toda lectura por ID usa `task_id + workspace_id`.
- UUID aleatorio, Task ajena, batch ajeno y filtros ajenos no revelan contenido.
- Los DTO `extra=forbid` rechazan Workspace, batch, resultado, resolución,
  actor, auditoría, capacidades, rol global y estructuras anidadas.
- La API solo expone creación puntual/recurrente, listado, detalle, patch,
  complete, not-complete y delete bajo `/api/v2/workspaces/{workspace_id}/tasks`.
- `TaskRead` proyecta estado, origen y capacidades; el frontend no fabrica
  privilegios. No expone `generation_batch_id` ni creador interno.

## Concurrencia y atomicidad

Las mutaciones usan locks y `lock_version`. Edición simultánea, resolución
competidora, delete versus update y alcances futuros no conservan estado ORM
obsoleto después de esperar. Una única operación gana y la otra recibe
conflicto. Colisiones puntuales o recurrentes revierten el lote: no quedan
Tasks parciales ni batches huérfanos. El service hace flush y la API conserva
commit/rollback.

## Listado, UX y privacidad de caché

El listado filtra en SQL por rango, Responsable, MasterTask, Categoría,
resultado/estado derivado y origen. Ordena por `planned_date,id`. En Shared el
selector contiene solo members activos del Workspace; Personal deriva al owner
sin selector innecesario. El cambio de Workspace desmonta el componente keyed,
limpia formularios, filtros, editores y diálogos; query keys contienen el
Workspace. Logout limpia toda la caché privada.

La vista desktop conserva tabla compacta y móvil transforma cada fila en tarjeta
vertical sin overflow horizontal. Formularios, labels, acciones y diálogos son
operables con teclado y mantienen nombres accesibles. Inicio, Revisión y Mi
calendario continúan siendo vistas globales, sin adquirir el filtro del
Workspace seleccionado.

## Evidencia

El cierre ejecuta tests Task de schemas, service, routes, recurrence, frontend,
autorización Workspace, seguridad del guard y PostgreSQL local desechable;
además ejecuta compilación Python, TypeScript, ESLint y build PWA. El guard
rechaza `lifemanager`, hosts remotos y nombres no allowlisted, y elimina cada
base desechable en `finally`.

No quedan findings HIGH abiertos del dominio Task.
