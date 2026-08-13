# Modelo físico objetivo de LifeManager V1 — Personal Workspace

## 1. Estado y autoridad

Este documento define el modelo físico objetivo aprobado para V1. Implementa `docs/requirements/Functional.md` y ADR-005; las decisiones físicas principales se registran en ADR-006. No describe necesariamente la base existente y no autoriza editar migraciones históricas.

El modelo legado está exclusivamente en `docs/database/Legacy-V1-Target-Data-Model.md`.

## 2. Principios

- UUID para claves primarias.
- `DATE` para fechas de negocio y `TIMESTAMPTZ` para eventos/auditoría.
- Datos raíz aislados por `workspace_id`.
- Estados derivados no persistidos.
- Restricciones DB para integridad de una fila; services/transacciones para reglas entre filas.
- Sin `TaskSeries`, recurrencia persistente, formulario genérico, relación Tarea–Proyecto ni historiales innecesarios.

Todas las tablas con auditoría estándar usan `id UUID PK`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` y `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. La aplicación actualiza `updated_at` en cada modificación.

## 3. Catálogo

| Entidad | Tabla | Propósito |
|---|---|---|
| User | `users` | Identidad, autenticación y zona horaria personal. |
| Workspace | `workspaces` | Límite de aislamiento; V1 crea uno Personal. |
| WorkspaceMember | `workspace_members` | Propiedad/autorización técnica. |
| WorkspaceTrackingMetadata | `workspace_tracking_metadata` | Timestamps operativos del Workspace. |
| Category | `categories` | Clasificación maestra. |
| MasterTask | `master_tasks` | Definición estandarizada de Tarea. |
| Task | `tasks` | Ocurrencia fechada de MasterTask. |
| PendingItem | `pending_items` | Pendiente con avance actual. |
| Project | `projects` | Objetivo compuesto por Pasos. |
| ProjectStep | `project_steps` | Unidad ponderada de un Proyecto. |

## 4. Infraestructura e identidad

### 4.1 `users`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `id` | UUID | no | PK |
| `email` | VARCHAR(255) | no | `UNIQUE`, valor normalizado en minúsculas |
| `hashed_password` | VARCHAR(255) | no | Nunca contraseña plana |
| `first_name` | VARCHAR(100) | no | no vacío |
| `last_name` | VARCHAR(100) | no | no vacío |
| `timezone` | VARCHAR(100) | no | IANA válida, validada por service |
| `is_active` | BOOLEAN | no | default `true` |
| `is_verified` | BOOLEAN | no | default `false` |
| auditoría estándar | — | — | — |

Índice único de email normalizado. `username`, `full_name`, `language` y settings heredados requieren evaluación/migración posterior; no pertenecen al objetivo funcional V1.

### 4.2 `workspaces`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `id` | UUID | no | PK |
| `name` | VARCHAR(150) | no | V1 usa `Personal` |
| `kind` | VARCHAR(20) | no | check `PERSONAL`, `COLLABORATIVE`; V1 crea `PERSONAL` |
| auditoría estándar | — | — | — |

`kind` distingue el Personal Workspace sin impedir V2. La regla “exactamente uno en V1” se garantiza en el service transaccional de registro: crea User, Workspace `PERSONAL` y membresía OWNER. No se impone “un workspace para siempre” en DB.

### 4.3 `workspace_members`

Conserva `id`, `workspace_id`, `user_id`, `role` y auditoría. Unique `(user_id, workspace_id)`; índices por ambas FK. En V1 solo se crea OWNER. Las capacidades colaborativas permanecen técnicas/futuras.

### 4.4 `workspace_tracking_metadata`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `workspace_id` | UUID | no | PK/FK `workspaces.id ON DELETE CASCADE` |
| `last_review_saved_at` | TIMESTAMPTZ | sí | solo Guardar revisión exitoso |
| `pending_items_last_tracking_saved_at` | TIMESTAMPTZ | sí | solo Guardar de Seguimiento > Pendientes |
| `created_at`, `updated_at` | TIMESTAMPTZ | no | auditoría |

Se usa una tabla 1:1 en vez de inflar Workspace con estado de módulos. `last_review_saved_at` es Workspace-level en V1 únicamente porque el Personal Workspace tiene exactamente un usuario/miembro activo en el producto. Esta ubicación no define la semántica colaborativa final de V2: antes de exponer Workspaces colaborativos deberá reevaluarse y probablemente migrarse o complementarse con metadata de revisión por `workspace_member`, para que la revisión de una persona no implique que las demás completaron la suya.

`pending_items_last_tracking_saved_at` sí puede continuar conceptualmente a nivel Workspace porque representa el último guardado del registro compartido de Seguimiento > Pendientes; aun así, su semántica deberá revisarse expresamente como parte del diseño colaborativo V2. Esta aclaración no introduce tablas V2 ni cambia el modelo o comportamiento V1 aprobado.

## 5. Datos maestros

### 5.1 Normalización común

El service limpia el nombre con Unicode NFC, trim y colapso de whitespace interno; `normalized_name` aplica `casefold` y nuevamente NFC. Así, `" Salir  a correr "` y `"SALIR A CORRER"` colisionan; acentos no se eliminan. Tanto visible como normalizado deben caber en su longitud.

### 5.2 `categories`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `workspace_id` | UUID | no | FK Workspace, cascade al borrar Workspace |
| `name` | VARCHAR(100) | no | check no vacío |
| `normalized_name` | VARCHAR(100) | no | unique `(workspace_id, normalized_name)` |
| auditoría estándar | — | — | — |

No hay descripción, Vigencia ni `is_used`. El uso se determina por referencias existentes desde MasterTask, PendingItem o Project. El service solo renombra/borra si ninguna existe; las FK usan `ON DELETE RESTRICT`, garantizando que una carrera no borre una Categoría usada.

### 5.3 `master_tasks`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `workspace_id` | UUID | no | FK Workspace |
| `category_id` | UUID | no | Categoría del mismo Workspace, `RESTRICT` |
| `name` | VARCHAR(150) | no | check no vacío |
| `normalized_name` | VARCHAR(150) | no | unique `(workspace_id, normalized_name)` |
| auditoría estándar | — | — | — |

No hay Vigencia ni descripción. El uso se determina con `EXISTS tasks WHERE master_task_id = id`. Una vez usada, el service impide todo update/delete; FK Task usa `RESTRICT`.

Task no guarda snapshot de Categoría: la inmutabilidad de MasterTask después del primer uso garantiza historia estable, evita redundancia y reporta mediante join MasterTask→Category.

## 6. `tasks`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `workspace_id` | UUID | no | FK Workspace |
| `master_task_id` | UUID | no | MasterTask del mismo Workspace, `RESTRICT` |
| `planned_date` | DATE | no | fecha de ocurrencia |
| `result` | VARCHAR(20) | sí | check `COMPLETED`, `NOT_COMPLETED` |
| `resolved_at` | TIMESTAMPTZ | sí | instante del resultado/corrección actual |
| `resolved_by_id` | UUID | sí | FK User `ON DELETE SET NULL` |
| `created_by_id` | UUID | sí | FK User `ON DELETE SET NULL` |
| `lock_version` | INTEGER | no | default 1, check >0 |
| auditoría estándar | — | — | — |

Check: resultado y `resolved_at` son ambos nulos o ambos no nulos; `resolved_by_id` solo puede existir con resultado. Unique `(workspace_id, master_task_id, planned_date)`.

La unicidad evita duplicados accidentales, vuelve idempotente la creación masiva y mantiene reportes por Tarea maestra comprensibles. Una necesidad futura de dos ocurrencias iguales deberá modelarse explícitamente, no mediante duplicados silenciosos.

### Estado y ciclo de vida

- `result IS NULL` y `planned_date > hoy local`: Programada.
- `result IS NULL` y `planned_date <= hoy local`: Pendiente.
- `COMPLETED`: Completada.
- `NOT_COMPLETED`: No Realizada.

Programada/Pendiente se calculan; no hay columna status. La primera resolución establece resultado, timestamp y actor. Una corrección cambia `COMPLETED ↔ NOT_COMPLETED`, renueva `resolved_at`/actor y nunca vuelve a null.

Solo el service puede borrar una fila con `result IS NULL AND planned_date > hoy local`. No existe borrado de registros históricos.

### Creación masiva

No existe entidad, FK ni procedencia de recurrencia. El request temporal valida rango/días, calcula fechas y en una transacción inserta Tasks. Antes de escribir detecta conflictos con el unique; el lote completo falla con un error claro si una fecha ya existe. No hay éxito parcial.

## 7. `pending_items`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `workspace_id` | UUID | no | FK Workspace |
| `category_id` | UUID | no | Categoría del mismo Workspace, `RESTRICT` |
| `name` | VARCHAR(255) | no | check no vacío |
| `is_active` | BOOLEAN | no | default `true` |
| `planned_date` | DATE | sí | obligatorio si activo; nulo si inactivo |
| `progress` | SMALLINT | no | default 0, check 0–100 |
| `completion_date` | DATE | sí | consistencia con progreso |
| `comment` | TEXT | sí | valor actual, no historial |
| `created_by_id` | UUID | sí | User `SET NULL` |
| `lock_version` | INTEGER | no | control optimista |
| auditoría estándar | — | — | — |

Checks: `NOT is_active OR planned_date IS NOT NULL`; `progress = 100` si y solo si `completion_date IS NOT NULL`. El service aplica además la regla de producto completa: desactivar limpia `planned_date`, reactivar requiere una nueva fecha desde Planificación y Seguimiento no puede asignarla. No hay descripción, tabla de progreso ni historial de comentarios.

Estado, Cumplimiento y Detalle son derivados. Al guardar 100 se asigna fecha local; al bajar se limpia; un 100 posterior usa la nueva fecha.

## 8. Proyectos

### 8.1 `projects`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `workspace_id` | UUID | no | FK Workspace |
| `category_id` | UUID | no | Categoría del mismo Workspace, `RESTRICT` |
| `name` | VARCHAR(255) | no | check no vacío |
| `is_active` | BOOLEAN | no | default `true` |
| `general_comment` | TEXT | sí | comentario actual |
| `last_tracking_saved_at` | TIMESTAMPTZ | sí | solo Guardar detalle de Seguimiento |
| `created_by_id` | UUID | sí | User `SET NULL` |
| `lock_version` | INTEGER | no | control optimista |
| auditoría estándar | — | — | — |

No almacena fecha planificada, progreso ni estado. Nombre único normalizado no se exige: los Proyectos son objetivos libres y pueden repetir nombre; `id` los distingue.

### 8.2 `project_steps`

| Columna | Tipo | Nulo | Regla |
|---|---|---:|---|
| `project_id` | UUID | no | FK Project `ON DELETE RESTRICT` |
| `name` | VARCHAR(255) | no | check no vacío |
| `planned_date` | DATE | sí | permite borrador inactivo; obligatorio al activar |
| `weight` | NUMERIC(5,2) | sí | permite borrador inactivo; check nulo o `>0 AND <=100` |
| `progress` | SMALLINT | no | default 0, check 0–100 |
| `completion_date` | DATE | sí | consistente con progreso |
| `comment` | TEXT | sí | valor actual |
| `position` | INTEGER | no | check >=0; unique `(project_id, position)` |
| `lock_version` | INTEGER | no | control optimista |
| auditoría estándar | — | — | — |

La DB valida filas; el service valida antes de activar/guardar estructura: al menos un Paso, todas las fechas, todos los pesos presentes y positivos, y suma exacta 100.00. La nulabilidad de fecha/peso permite Pasos incompletos únicamente mientras el Proyecto está inactivo. ProjectStep no se relaciona con Task/MasterTask.

Para una estructura completa: Fecha planificada de Proyecto = `max(step.planned_date)`. Avance = `sum(weight * progress) / 100`. Estado: todos 0 No iniciado; todos 100 Finalizado; otro caso En proceso. Un Proyecto inactivo con estructura incompleta no publica estos derivados como si fueran definitivos. No se persisten.

## 9. Cumplimiento y Detalle derivados

Aplica a PendingItem y ProjectStep con fecha planificada.

| Condición | Cumplimiento | Diferencia entera |
|---|---|---:|
| sin finalizar, `planned_date >= today` | EN_PLAZO | `planned_date - today` días restantes |
| sin finalizar, `planned_date < today` | ATRASADO | `today - planned_date` días de atraso |
| finalizado antes | CON_ADELANTO | `planned_date - completion_date` |
| finalizado igual | A_TIEMPO | 0 |
| finalizado después | CON_RETRASO | `completion_date - planned_date` |

La diferencia es entre fechas calendario, exclusiva del día inicial: plan 10 y evaluación 11 = 1 día. No se almacena clasificación, diferencia ni texto; SQL puede calcularlos para filtros/reportes.

## 10. Transacciones y concurrencia

Guardar Revisión ejecuta en una transacción: valida membresía, fecha efectiva y versiones; bloquea/actualiza Tasks, PendingItems y ProjectSteps; deriva fechas de cumplimiento; actualiza `last_review_saved_at`; flush/commit único. Cualquier error revierte todo.

Guardar Seguimiento > Pendientes actualiza todas las filas y `pending_items_last_tracking_saved_at` atómicamente. Guardar detalle de Proyecto actualiza sus Pasos y `project.last_tracking_saved_at` atómicamente. Editar `general_comment` es un update normal y no cambia ese timestamp.

Cada payload mutable incluye `lock_version` esperado. El update usa `WHERE id=? AND lock_version=?`, incrementándolo; cero filas produce conflicto 409 y evita sobrescribir cambios. En batch, un solo conflicto revierte el lote.

## 11. Aislamiento y FKs

Cada raíz tiene `workspace_id`. Para relaciones críticas se añade `UNIQUE(id, workspace_id)` al padre y FK compuesta:

- `master_tasks(category_id, workspace_id) → categories(id, workspace_id)`;
- `tasks(master_task_id, workspace_id) → master_tasks(id, workspace_id)`;
- `pending_items(category_id, workspace_id) → categories(id, workspace_id)`;
- `projects(category_id, workspace_id) → categories(id, workspace_id)`.

Esto impide referencias cruzadas incluso ante un bug del service. ProjectStep hereda Workspace mediante su Project y no duplica `workspace_id`. Todas las consultas siguen requiriendo scope/autorización en service.

Workspace→datos usa `CASCADE` para eliminación deliberada de cuenta/Workspace. User actor FKs usan `SET NULL` para preservar historia. Category/MasterTask/Project→registros históricos usa `RESTRICT`.

## 12. Índices

| Tabla | Índice | Consulta |
|---|---|---|
| Category | unique `(workspace_id, normalized_name)` | lookup/duplicados |
| MasterTask | unique `(workspace_id, normalized_name)` | selector/reportes |
| MasterTask | `(workspace_id, category_id, name)` | filtro por Categoría |
| Task | unique `(workspace_id, master_task_id, planned_date)` | idempotencia |
| Task | `(workspace_id, planned_date DESC, id)` | Seguimiento/rango |
| Task | `(workspace_id, result, planned_date DESC)` | Revisión/resultado |
| PendingItem | `(workspace_id, is_active, planned_date, id)` | vista inicial/Revisión |
| PendingItem | `(workspace_id, category_id, planned_date)` | filtros/reportes |
| Project | `(workspace_id, is_active, category_id, name)` | listado/filtros |
| ProjectStep | unique `(project_id, position)` | orden estable |
| ProjectStep | `(planned_date, progress, project_id)` | Revisión vía join Project |

No se indexan estados/progreso derivados de Proyecto. Las consultas agregadas usarán joins y podrán justificar índices adicionales con `EXPLAIN`/carga real.

## 13. Inmutabilidad y borrado

- Category: renombrar/borrar solo sin referencias; después inmutable.
- MasterTask: editar/borrar solo sin Tasks; después inmutable.
- Task: borrar solo Programada sin resultado; históricas restringidas.
- PendingItem: recomendación de seguridad V1: borrar solo si nunca tuvo avance (`0`), completion ni comentario; en otro caso conservar y desactivar.
- Project: borrar solo inactivo, sin tracking/comentarios y con Pasos sin avance/comentario; en otro caso conservar inactivo.
- ProjectStep: borrar/reordenar desde Planificación solo mientras el Proyecto está inactivo o antes de cualquier tracking; después se conserva.

Las tres últimas son decisiones técnicas conservadoras de integridad ante silencios funcionales; no agregan estado Cancelada ni historial.

## 14. Representaciones físicas

- Task result: `VARCHAR(20)` nullable + check, no PostgreSQL ENUM, para migraciones simples.
- Vigencia: BOOLEAN `is_active` en PendingItem/Project.
- Estados y Cumplimiento derivados: no columnas/enums.
- Pesos: `NUMERIC(5,2)` para suma exacta 100.00.
- Actor IDs: `created_by_id` en recursos operativos y `resolved_by_id` en Task; no `updated_by` general sin auditoría histórica.
- Zona horaria: solo `User.timezone` en V1. Una futura zona operativa de Workspace podrá añadirse en V2 sin cambiar las fechas de negocio ya persistidas.

## 15. Transición de esquema

Todo contenido anterior al refactor aprobado es dato descartable de desarrollo/prueba. No se realizan backfills ni compatibilidad de registros legados. Stage 4 implementa el objetivo mediante revisiones nuevas: un reset controlado del esquema de aplicación y la creación directa del dominio V1.

Ninguna migración histórica de Alembic se edita o elimina. La cadena completa debe producir este modelo tanto desde una base vacía como al avanzar desde el head legado. El reset destructivo exige una base local de desarrollo/prueba identificada explícitamente y nunca afecta infraestructura PostgreSQL ajena a LifeManager.
