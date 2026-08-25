# Modelo lógico y físico objetivo de LifeManager V2.0.0

## Estado y autoridad

Este documento es el diseño de datos autoritativo para implementar LifeManager V2.0.0. Traduce `docs/requirements/Functional-V2.md` y ADR-007 a un modelo lógico/físico PostgreSQL. ADR-008 registra sus decisiones principales.

El modelo **no está implementado**. No describe el runtime V1, no autoriza migraciones y no modifica la base de datos. El esquema V1 permanece documentado separadamente en `V1-Target-Data-Model.md` y `ERD.md`.

## 1. Decisiones generales

- PostgreSQL, SQLAlchemy 2.x y Alembic continúan.
- Las PK son UUID y las entidades mutables conservan `created_at`/`updated_at` como `TIMESTAMPTZ`.
- Los enums de dominio se implementan como `VARCHAR` con `CHECK` y enums de aplicación. Esto evita el costo de alterar tipos PostgreSQL nativos durante la evolución V2.
- Todo recurso de negocio posee `workspace_id`, directamente o mediante un padre cuya FK lo hace inequívoco.
- Las asignaciones usan `(workspace_id, user_id)` contra `workspace_members`, no un FK aislado a `users`.
- `WorkspaceMember` no se borra al salir: cambia de estado y preserva identidad histórica.
- Los actores históricos referencian `users` con `ON DELETE RESTRICT`; una cuenta se deshabilita, no se borra si tiene historia.
- Valores confiablemente derivables no se duplican.
- Entidades mutables expuestas a edición concurrente usan `lock_version`; eventos, tokens e historiales inmutables no.
- La recurrencia genera ocurrencias materiales finitas. Un grupo inmutable conserva procedencia para operaciones futuras, pero no sincroniza ni redefine ocurrencias históricas.

En las tablas donde se indica **auditoría**, se incluyen `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` y `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`; el ORM actualiza `updated_at`. Las tablas declaradas inmutables conservan solo el timestamp explícito indicado.

## 2. Inventario de entidades

| Área | Entidades |
|---|---|
| Identidad | User, UserAccountStateEvent, AccountActionToken |
| Colaboración | Workspace, WorkspaceMember, WorkspaceInvitation |
| Catálogos | Category, MasterTask, ActivityMaster |
| Generación | GenerationBatch |
| Tareas | Task |
| Pendientes | PendingItem, PendingItemHistory |
| Proyectos | Project, ProjectLeaderHistory, ProjectStage, ProjectStageHistory |
| Calendario | Activity, ActivityParticipant, ActivityReminder |
| Revisión/preferencias | UserReviewMetadata, ReminderPreference |
| Notificaciones | Notification, PushSubscription, NotificationDelivery |

## 3. Identidad y cuenta

### 3.1 `users`

Una fila representa una identidad de plataforma, independientemente de sus membresías.

| Columna | Tipo | Nulabilidad/default | Regla |
|---|---|---|---|
| `id` | UUID | PK | BaseEntity |
| `email` | VARCHAR(255) | NOT NULL | correo normalizado en minúsculas |
| `hashed_password` | VARCHAR(255) | NOT NULL | nunca contraseña plana |
| `first_name` | VARCHAR(100) | NOT NULL | no vacío |
| `last_name` | VARCHAR(100) | NOT NULL | no vacío |
| `timezone` | VARCHAR(100) | NOT NULL, `America/Lima` | identificador IANA validado por aplicación |
| `account_status` | VARCHAR(32) | NOT NULL, `PENDING_EMAIL_VERIFICATION` | estado exclusivo de cuenta |
| `global_role` | VARCHAR(32) | NULL | solo `GLOBAL_ADMIN` en V2 |
| `email_verified_at` | TIMESTAMPTZ | NULL | presente desde verificación válida |
| `status_changed_at` | TIMESTAMPTZ | NOT NULL, `now()` | auditoría del estado actual |
| `lock_version` | INTEGER | NOT NULL, 1 | positivo |
| `created_at`, `updated_at` | TIMESTAMPTZ | NOT NULL | auditoría |

Estados: `PENDING_EMAIL_VERIFICATION`, `PENDING_APPROVAL`, `ACTIVE`, `REJECTED`, `DISABLED`.

Restricciones e índices:

- `UNIQUE (email)` e índice de login por `email`.
- `CHECK` de email/nombres no vacíos y `lock_version > 0`.
- `CHECK`: `PENDING_EMAIL_VERIFICATION` exige `email_verified_at IS NULL`; los demás estados exigen verificación.
- `CHECK`: `global_role IS NULL OR global_role = 'GLOBAL_ADMIN'`.
- índice único parcial sobre `global_role` donde sea `GLOBAL_ADMIN`, para una sola administración global inicial.
- `full_name` se deriva de nombres; no se persisten `username` ni `language` sin requisito V2.

Una cuenta con historia no se elimina: pasa a `DISABLED`. El flujo aprobado avanza de verificación a aprobación; rechazo y deshabilitación son estados explícitos, no combinaciones de booleanos.

Transiciones permitidas: PENDING_EMAIL_VERIFICATION → PENDING_APPROVAL; PENDING_APPROVAL → ACTIVE o REJECTED; ACTIVE → DISABLED; DISABLED → ACTIVE mediante acción administrativa. Cambiar el email invalida tokens anteriores, limpia `email_verified_at` y vuelve a PENDING_EMAIL_VERIFICATION en una transacción auditada.

### 3.2 `user_account_state_events`

Auditoría inmutable de aprobación, rechazo, activación y deshabilitación.

`id UUID PK`, `user_id UUID NOT NULL FK users RESTRICT`, `from_status VARCHAR(32) NULL`, `to_status VARCHAR(32) NOT NULL`, `actor_user_id UUID NULL FK users RESTRICT`, `reason TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL`.

Índice `(user_id, created_at DESC, id)`. No tiene `updated_at` ni `lock_version`; no se edita ni borra en operación normal. La aprobación global queda atribuida mediante `actor_user_id`.

### 3.3 `account_action_tokens`

Token de un solo uso para `EMAIL_VERIFICATION` o `PASSWORD_RESET`.

`id UUID PK`, `user_id UUID NOT NULL FK users CASCADE`, `token_type VARCHAR(32) NOT NULL`, `token_digest BYTEA NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`, `consumed_at TIMESTAMPTZ NULL`, `revoked_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL`.

- Se almacena únicamente un digest criptográfico, nunca el token utilizable.
- `UNIQUE (token_digest)`.
- índice `(user_id, token_type, expires_at)`.
- índice único parcial `(user_id, token_type)` donde `consumed_at` y `revoked_at` son NULL para un token activo de cada tipo.
- `CHECK expires_at > created_at` y `CHECK NOT (consumed_at IS NOT NULL AND revoked_at IS NOT NULL)`.
- Consumo/revocación se realiza con update condicional para garantizar un solo uso.

## 4. Workspaces, membresía e invitaciones

### 4.1 `workspaces`

`id UUID PK`, `name VARCHAR(150) NOT NULL`, `kind VARCHAR(20) NOT NULL`, `owner_user_id UUID NOT NULL FK users RESTRICT`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

Kinds: `PERSONAL`, `SHARED`.

- `owner_user_id` es la única fuente de propiedad; WorkspaceMember no almacena rol.
- índice único parcial `(owner_user_id)` donde `kind='PERSONAL'`, garantizando como máximo un Personal Workspace por usuario.
- `CHECK` nombre no vacío y versión positiva.
- índice `(owner_user_id, kind, id)`; no se exige unicidad de nombres de Workspace.
- un trigger de restricción PostgreSQL, diferible al final de la transacción, exige que `(id, owner_user_id)` corresponda a una membresía `ACTIVE`. Esto permite aprovisionar Workspace+membresía atómicamente sin duplicar propiedad.

El service de registro crea exactamente un Personal Workspace al activar/aprovisionar la cuenta. La unicidad parcial evita duplicarlo; la existencia para toda cuenta ACTIVE se valida en el flujo transaccional y pruebas de integridad.

La clase de Workspace no se infiere del nombre. `PERSONAL` es inmutable en las operaciones ordinarias: no admite miembros distintos del owner, transferencia, conversión ni eliminación. La membresía `ACTIVE` del owner tampoco puede finalizar mientras conserve la propiedad. Estas reglas de operación se aplican en la frontera central de servicio; el índice único parcial y el trigger diferible permanecen como garantías finales de unicidad y consistencia owner/membership. `SHARED` admite colaboración futura, pero su creación, invitaciones, administración de miembros y transferencia se implementan en etapas posteriores.

### 4.2 `workspace_members`

Una fila permanente representa la relación histórica de una persona con un Workspace.

`id UUID PK`, `workspace_id UUID NOT NULL FK workspaces CASCADE`, `user_id UUID NOT NULL FK users RESTRICT`, `status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'`, `calendar_visibility VARCHAR(24) NOT NULL DEFAULT 'HIDE'`, `joined_at TIMESTAMPTZ NOT NULL`, `ended_at TIMESTAMPTZ NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- `UNIQUE (workspace_id, user_id)`; una reincorporación reactiva la misma identidad de membresía.
- `UNIQUE (id, workspace_id)` para referencias compuestas cuando convenga.
- `CHECK status IN ('ACTIVE','LEFT','REMOVED')`.
- `CHECK`: ACTIVE exige `ended_at IS NULL`; LEFT/REMOVED exigen `ended_at IS NOT NULL`.
- privacidad: `SHOW_DETAILS`, `AVAILABILITY_ONLY`, `HIDE`.
- índices `(user_id, status, workspace_id)` para selector y `(workspace_id, status, user_id)` para administración/asignaciones.

El rol visible se deriva: si `user_id = workspace.owner_user_id`, Propietario; en otro caso, Miembro. `ADMIN` y `VIEWER` no forman parte del modelo V2.

### 4.3 `workspace_invitations`

`id UUID PK`, `workspace_id UUID NOT NULL FK workspaces CASCADE`, `recipient_email VARCHAR(255) NOT NULL`, `recipient_user_id UUID NULL FK users RESTRICT`, `inviter_user_id UUID NOT NULL`, `status VARCHAR(16) NOT NULL DEFAULT 'PENDING'`, `token_digest BYTEA NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`, `responded_at TIMESTAMPTZ NULL`, `cancelled_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL`.

`(workspace_id, inviter_user_id)` referencia una membresía del Workspace; el service exige que sea la persona autorizada. Restricciones:

- estados `PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `CANCELLED`;
- `UNIQUE (token_digest)`;
- índice único parcial `(workspace_id, recipient_email)` donde status=`PENDING`;
- índice `(recipient_user_id, status, created_at DESC)` e índice `(expires_at)` para expiración;
- aceptación bloquea invitación y Workspace, crea/reactiva WorkspaceMember y marca `ACCEPTED` en una transacción;
- no se reutiliza para Participantes de Actividad.

En V2.0.0 solo se invita a una cuenta `ACTIVE` existente y `recipient_user_id` queda siempre vinculado al crear. La vigencia es de 14 días. La aceptación se autentica por sesión contra ese destinatario, no mediante token entregado: se genera material aleatorio únicamente para satisfacer el digest físico, sin persistir ni retornar el valor crudo. Una reincorporación `LEFT` o `REMOVED` reutiliza la fila, fija `ACTIVE`, reinicia `joined_at`, limpia `ended_at`, restablece `calendar_visibility=HIDE` e incrementa `lock_version`. Los PENDING vencidos se filtran de listados accionables y se terminalizan al crear una nueva invitación para el mismo destinatario; no requieren scheduler.

## 5. Categorías y catálogos

### 5.1 `categories`

`id UUID PK`, `workspace_id UUID NOT NULL FK workspaces CASCADE`, `name VARCHAR(100) NOT NULL`, `normalized_name VARCHAR(100) NOT NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- `UNIQUE (workspace_id, normalized_name)` y `UNIQUE (id, workspace_id)`.
- nombre no vacío, versión positiva.
- índice `(workspace_id, is_active, normalized_name, id)`.
- usada: se desactiva, no se borra. Sin uso: hard delete permitido.

### 5.2 `master_tasks`

`id UUID PK`, `workspace_id UUID NOT NULL`, `category_id UUID NOT NULL`, `name VARCHAR(150) NOT NULL`, `normalized_name VARCHAR(150) NOT NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- FK compuesta `(category_id, workspace_id) → categories(id, workspace_id) ON DELETE RESTRICT`.
- `UNIQUE (workspace_id, normalized_name)`, `UNIQUE (id, workspace_id)`.
- índice `(workspace_id, is_active, category_id, normalized_name, id)`.
- los usados se desactivan, no se borran.
- cambiar `category_id` reclasifica deliberadamente todas las ocurrencias históricas; Task no guarda Category.

### 5.3 `activity_masters`

Misma estructura y política que MasterTask, en tabla separada. `name VARCHAR(150)`, Category workspace-aware, Active/Inactive, versión, `UNIQUE (workspace_id, normalized_name)` e índice `(workspace_id, is_active, category_id, normalized_name, id)`.

ActivityMaster no se comparte con MasterTask. Las Actividades históricas derivan su Category actual del master, pero preservan el nombre visible como snapshot en Activity.

## 6. Generación finita

### 6.1 `generation_batches`

Registro inmutable de procedencia, no plantilla editable ni fuente de sincronización.

`id UUID PK`, `workspace_id UUID NOT NULL FK workspaces CASCADE`, `entity_type VARCHAR(16) NOT NULL`, `pattern VARCHAR(16) NOT NULL`, `date_from DATE NOT NULL`, `date_until DATE NOT NULL`, `weekdays SMALLINT[] NULL`, `month_days SMALLINT[] NULL`, `timezone VARCHAR(100) NULL`, `created_by_user_id UUID NOT NULL`, `created_at TIMESTAMPTZ NOT NULL`.

- FK compuesta de creador a membresía del Workspace.
- `entity_type IN ('TASK','ACTIVITY')`; pattern `DAILY`, `WEEKLY`, `MONTHLY`.
- `UNIQUE (id, workspace_id)` para referencias compuestas desde ocurrencias.
- `date_until >= date_from`.
- DAILY: ambos arrays NULL.
- WEEKLY: `weekdays` no vacío, único, valores 0–6; `month_days` NULL.
- MONTHLY: `month_days` no vacío, único, valores 1–31; `weekdays` NULL.
- los checks de unicidad/rango de arrays se implementan mediante funciones SQL inmutables pequeñas usadas por CHECK; el service valida antes, pero la DB sigue siendo el límite final.
- Task usa timezone NULL porque opera con DATE; Activity exige la zona IANA utilizada para convertir fechas/horas locales a instantes UTC, preservando reproducibilidad ante DST.
- índice `(workspace_id, entity_type, created_at DESC)`.

Las ocurrencias son materiales e independientes. El batch permite `Todas las futuras`, eliminación/reasignación masiva y trazabilidad. No propaga ediciones, no cambia fechas ya generadas y no se reactiva/extiende como una serie.

La generación calcula fechas primero, aplica fallback al último día del mes conservando cada día ancla original, deduplica colisiones —por ejemplo 29/30/31 en febrero— y luego inserta. Las constraints finales de Task/Activity mantienen idempotencia.

## 7. Tareas

### 7.1 `tasks`

`id UUID PK`, `workspace_id UUID NOT NULL`, `master_task_id UUID NOT NULL`, `responsible_user_id UUID NOT NULL`, `planned_date DATE NOT NULL`, `result VARCHAR(20) NULL`, `resolved_at TIMESTAMPTZ NULL`, `resolved_by_user_id UUID NULL`, `created_by_user_id UUID NOT NULL`, `generation_batch_id UUID NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

Integridad:

- FK `workspace_id → workspaces ON DELETE CASCADE`.
- FK compuesta `(master_task_id, workspace_id) → master_tasks(id, workspace_id) RESTRICT`.
- FK compuesta `(workspace_id, responsible_user_id) → workspace_members(workspace_id, user_id) RESTRICT`.
- FKs compuestas equivalentes para creador y resolvedor; el resolvedor es nullable.
- FK compuesta `(generation_batch_id, workspace_id) → generation_batches(id, workspace_id) RESTRICT`; exige `entity_type=TASK` mediante trigger/service.
- `UNIQUE (workspace_id, master_task_id, planned_date, responsible_user_id)`.
- `result IS NULL OR result IN ('COMPLETED','NOT_COMPLETED')`.
- resultado NULL implica resolved_at/resolved_by NULL; resultado terminal exige ambos.
- versión positiva.

Índices:

- `(responsible_user_id, result, planned_date, workspace_id, id)` para Revisión global.
- `(workspace_id, planned_date DESC, id)` para registro.
- `(workspace_id, master_task_id, planned_date DESC)` para reportes.
- `(generation_batch_id, planned_date, id)` donde batch no sea NULL.

`PROGRAMADA` y `PENDIENTE` se derivan de `planned_date`, resultado y fecha local del usuario. MasterTask y Category no se copian. Las ocurrencias resueltas son históricamente estables; correcciones autorizadas son updates optimistas auditables por actor/fecha de resolución.

## 8. Pendientes e historia

### 8.1 `pending_items`

`id UUID PK`, `workspace_id UUID NOT NULL`, `category_id UUID NOT NULL`, `responsible_user_id UUID NOT NULL`, `name VARCHAR(255) NOT NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `planned_date DATE NULL`, `progress SMALLINT NOT NULL DEFAULT 0`, `completion_date DATE NULL`, `created_by_user_id UUID NOT NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- Category, Responsible y creador usan FKs compuestas workspace-aware.
- `UNIQUE (id, workspace_id)` para la historia workspace-aware.
- Activo exige planned_date; inactivo exige planned_date NULL.
- progreso 0–100; 100 exige completion_date, menos de 100 exige NULL.
- índice `(responsible_user_id, is_active, progress, planned_date, workspace_id, id)` para Revisión.
- índices `(workspace_id, is_active, planned_date, id)` y `(workspace_id, category_id, planned_date)`.

Estado y Cumplimiento son derivados. El comentario corriente no se guarda en PendingItem: la entrada histórica más reciente aporta el comentario visible cuando se necesite.

### 8.2 `pending_item_history`

`id UUID PK`, `pending_item_id UUID NOT NULL FK pending_items RESTRICT`, `workspace_id UUID NOT NULL`, `actor_user_id UUID NOT NULL`, `progress SMALLINT NOT NULL`, `comment TEXT NULL`, `event_type VARCHAR(16) NOT NULL`, `recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

- FKs compuestas preservan Workspace para PendingItem y actor.
- progreso 0–100; `event_type IN ('TRACKING','CORRECTION')`.
- `CHECK comment IS NULL OR length(btrim(comment)) > 0`.
- índice `(pending_item_id, recorded_at DESC, id)` y `(workspace_id, recorded_at DESC)` para reportes.
- append-only, sin `updated_at` ni versión.

Cada guardado que cambia progreso crea entrada. Un comentario no vacío sin cambio de progreso también crea entrada. Un no-op sin cambio ni comentario se rechaza. Item actual e historia se actualizan/inserta atómicamente.

## 9. Proyectos, Etapas e historia

### 9.1 `projects`

`id UUID PK`, `workspace_id UUID NOT NULL`, `category_id UUID NOT NULL`, `leader_user_id UUID NOT NULL`, `name VARCHAR(255) NOT NULL`, `description TEXT NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `created_by_user_id UUID NOT NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- Category, Líder y creador con FKs compuestas workspace-aware.
- `UNIQUE (id, workspace_id)` para Etapas e historia de liderazgo.
- nombre no vacío, versión positiva.
- índices `(workspace_id, is_active, category_id, name, id)` y `(leader_user_id, is_active, workspace_id, id)`.
- fecha planificada, progreso, estado, cumplimiento y fecha de cumplimiento se derivan de Etapas válidas; no se almacenan.

### 9.2 `project_leader_history`

Auditoría inmutable de cada asignación o reasignación de Líder: `id UUID PK`, `project_id UUID NOT NULL`, `workspace_id UUID NOT NULL`, `leader_user_id UUID NOT NULL`, `actor_user_id UUID NOT NULL`, `recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

- FK compuesta a Project y FKs compuestas de Líder/actor a membresía del Workspace.
- índice `(project_id, recorded_at DESC, id)`.
- al crear o cambiar `projects.leader_user_id`, se inserta este evento en la misma transacción.
- Project mantiene el líder corriente para consultas; el historial preserva atribución anterior sin convertirse en un sistema conversacional.

### 9.3 `project_stages`

Nombre técnico recomendado: `ProjectStage`/`project_stages`. V2 debe alinear código nuevo con “Etapa”; no existe obligación de conservar `ProjectStep` porque el esquema V2 se reinicia.

`id UUID PK`, `workspace_id UUID NOT NULL`, `project_id UUID NOT NULL`, `responsible_user_id UUID NOT NULL`, `name VARCHAR(255) NOT NULL`, `position INTEGER NOT NULL`, `weight NUMERIC(5,2) NOT NULL`, `planned_date DATE NOT NULL`, `progress SMALLINT NOT NULL DEFAULT 0`, `completion_date DATE NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- `UNIQUE (project_id, position)` y `UNIQUE (id, workspace_id)`.
- FK compuesta `(project_id, workspace_id) → projects(id, workspace_id) CASCADE`.
- Responsable con FK de membresía workspace-aware.
- posición >= 0, peso > 0 y <= 100, progreso 0–100, consistencia de completion_date, versión positiva.
- índices `(project_id, position, id)` y `(responsible_user_id, progress, planned_date, workspace_id, id)`.

La suma exacta 100.00 es una invariancia transversal: se valida al activar/guardar estructura bajo lock de Project, no mediante CHECK por fila. Lock canónico: Project primero, Etapas por ID después.

### 9.4 `project_stage_history`

Equivalente a PendingItemHistory: `id`, `project_stage_id`, `workspace_id`, `actor_user_id`, `progress`, `comment`, `event_type`, `recorded_at`. FKs compuestas, checks, append-only e índices `(project_stage_id, recorded_at DESC, id)` y `(workspace_id, recorded_at DESC)`.

No existe un segundo sistema de comentarios. Cada cambio de avance o comentario no vacío crea un evento; el estado actual de avance permanece en ProjectStage para consultas eficientes.

## 10. Actividades, participantes y recordatorios

### 10.1 `activities`

`id UUID PK`, `workspace_id UUID NOT NULL`, `organizer_user_id UUID NOT NULL`, `activity_master_id UUID NULL`, `title VARCHAR(255) NOT NULL`, `custom_category_id UUID NULL`, `starts_at TIMESTAMPTZ NOT NULL`, `ends_at TIMESTAMPTZ NOT NULL`, `status VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED'`, `cancelled_at TIMESTAMPTZ NULL`, `cancelled_by_user_id UUID NULL`, `generation_batch_id UUID NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- Organizador con FK compuesta a membresía.
- Master con FK compuesta al Workspace; Category custom igual.
- XOR: con master, `custom_category_id IS NULL`; sin master, Category explícita obligatoria.
- `title` siempre es snapshot: para master copia el nombre al crear; así un rename no reescribe historia. Category sí se deriva dinámicamente de ActivityMaster. Para custom, title y Category son explícitos.
- `ends_at > starts_at`.
- status `SCHEDULED` o `CANCELLED`; cancelación guarda `cancelled_at` y `cancelled_by_user_id` en columnas nullable con consistencia.
- `UNIQUE (id, workspace_id)` para Participantes y reminders workspace-aware.
- batch con entity_type ACTIVITY.
- índices GiST sobre `tstzrange(starts_at, ends_at, '[)')` junto a `workspace_id` cuando `btree_gist` esté aprobado, o B-tree `(workspace_id, starts_at, ends_at)` como mínimo.
- índices `(organizer_user_id, starts_at, id)` y `(generation_batch_id, starts_at, id)`.
- índice único parcial `(generation_batch_id, starts_at)` donde batch no sea NULL para deduplicar colisiones.

No se aplica exclusión de solapamiento: el producto puede permitir eventos simultáneos y solo necesita mostrar disponibilidad.

Una Activity pasada es inmutable. Solo el Organizador puede modificar/cancelar una futura para todos; “Todas las futuras” selecciona ocurrencias no pasadas del mismo GenerationBatch y actualiza cada fila con locking optimista, sin cambiar las anteriores.

### 10.2 `activity_participants`

`id UUID PK`, `activity_id UUID NOT NULL`, `workspace_id UUID NOT NULL`, `user_id UUID NOT NULL`, `calendar_status VARCHAR(16) NOT NULL DEFAULT 'VISIBLE'`, `removed_at TIMESTAMPTZ NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- `UNIQUE (activity_id, user_id)`.
- FK Activity+Workspace y membresía Workspace+User.
- `VISIBLE` exige removed_at NULL; `REMOVED` exige timestamp.
- índice `(user_id, calendar_status, activity_id)` y, mediante join con Activity, consulta por rango.
- el Organizador es autoridad separada y no se duplica como participante; puede tener su propio ActivityReminder.
- retirar del calendario cambia a REMOVED y desactiva su recordatorio en una transacción. La fila se conserva.

### 10.3 `activity_reminders`

Configuración por usuario y ocurrencia: `id UUID PK`, `activity_id UUID NOT NULL`, `workspace_id UUID NOT NULL`, `user_id UUID NOT NULL`, `minutes_before INTEGER NOT NULL`, `is_enabled BOOLEAN NOT NULL DEFAULT true`, `last_scheduled_for TIMESTAMPTZ NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- `UNIQUE (activity_id, user_id)`.
- FKs workspace-aware a Activity y membresía.
- `CHECK minutes_before >= 0`; un límite operacional superior será configurable y validado por service, no una regla permanente de producto.
- índice de scheduling `(is_enabled, last_scheduled_for, activity_id)`; el scheduler derivará la próxima hora desde Activity.
- Participante REMOVED o Activity CANCELLED fuerza `is_enabled=false`.

No se necesita default global en Activity: al crear se materializa una preferencia por cada persona que elija recordatorio, incluido Organizador. Esto evita que un cambio global altere preferencias individuales.

## 11. Privacidad y disponibilidad

`calendar_visibility` vive en WorkspaceMember porque expresa la política de una persona frente a los miembros de ese Workspace. Se aplica al calendario consolidado de esa persona, no solo a Activities del Workspace.

La comparación obtiene membresías activas y su política, luego deriva intervalos desde Activities donde la persona sea Organizador o Participante VISIBLE. No se guardan slots de disponibilidad. Los intervalos se calculan por rango temporal y se fusionan en aplicación/SQL según necesidad.

## 12. Metadata de Revisión

### 12.1 `user_review_metadata`

Una fila global por usuario: `user_id UUID PK FK users CASCADE`, `tasks_last_saved_at TIMESTAMPTZ NULL`, `pending_items_last_saved_at TIMESTAMPTZ NULL`, `project_stages_last_saved_at TIMESTAMPTZ NULL`, `updated_at TIMESTAMPTZ NOT NULL`.

Cada bloque actualiza solo su timestamp después de su propia transacción exitosa. No hay `workspace_id`: Revisión agrega asignaciones entre Workspaces. Una persona nunca marca la revisión de otra. Los cambios concretos permanecen en Task o en las historias de Pendiente/Etapa, evitando duplicar checklist items.

## 13. Preferencias de recordatorio

### 13.1 `reminder_preferences`

Una tabla limitada a cuatro comportamientos conocidos: `id UUID PK`, `user_id UUID NOT NULL FK users CASCADE`, `reminder_type VARCHAR(32) NOT NULL`, `is_enabled BOOLEAN NOT NULL DEFAULT false`, `schedule_kind VARCHAR(16) NOT NULL`, `local_time TIME NOT NULL`, `weekdays SMALLINT[] NULL`, `month_days SMALLINT[] NULL`, `lock_version INTEGER NOT NULL DEFAULT 1`, auditoría.

- `UNIQUE (user_id, reminder_type)`.
- tipos: `DAILY_SUMMARY`, `DAILY_REVIEW`, `PENDING_FOLLOW_UP`, `PROJECT_FOLLOW_UP`.
- los dos primeros exigen schedule_kind DAILY y arrays NULL.
- follow-up admite DAILY, WEEKLY o MONTHLY con las mismas reglas de arrays que GenerationBatch.
- los mismos helpers SQL inmutables protegen rango y ausencia de duplicados en weekdays/month_days.
- índice `(is_enabled, reminder_type, local_time)` para barrido; el instante se calcula con `users.timezone` y manejo explícito de DST.

No se crea un scheduler genérico ni campos Desde/Hasta.

## 14. Notificaciones y Web Push

### 14.1 `notifications`

`id UUID PK`, `recipient_user_id UUID NOT NULL FK users RESTRICT`, `actor_user_id UUID NULL FK users RESTRICT`, `workspace_id UUID NULL FK workspaces SET NULL`, `notification_type VARCHAR(48) NOT NULL`, `title VARCHAR(160) NOT NULL`, `body TEXT NOT NULL`, `deep_link VARCHAR(500) NULL`, `payload JSONB NOT NULL DEFAULT '{}'`, `dedup_key VARCHAR(255) NULL`, `read_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL`, `expires_at TIMESTAMPTZ NULL`.

- contenido es texto plano; payload usa esquema/allowlist por tipo, nunca HTML arbitrario ni secretos.
- índice único parcial `(recipient_user_id, dedup_key)` donde dedup_key no sea NULL.
- índice parcial `(recipient_user_id, created_at DESC, id)` donde `read_at IS NULL` e índice general para historial.
- un batch recurrente usa un dedup_key lógico y genera una sola notificación.
- retención: expiración configurable y hard delete por job; eventos de auditoría no dependen de Notification.

### 14.2 `push_subscriptions`

`id UUID PK`, `user_id UUID NOT NULL FK users CASCADE`, `endpoint_ciphertext BYTEA NOT NULL`, `endpoint_hash BYTEA NOT NULL`, `p256dh_ciphertext BYTEA NOT NULL`, `auth_ciphertext BYTEA NOT NULL`, `user_agent VARCHAR(500) NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `last_success_at TIMESTAMPTZ NULL`, `invalidated_at TIMESTAMPTZ NULL`, auditoría.

- `UNIQUE (endpoint_hash)`; el hash identifica y los valores cifrados permiten enviar.
- índice `(user_id, is_active, id)`.
- secretos cifrados con clave fuera de DB y nunca devueltos a otros usuarios/logs.
- invalidación desactiva; el usuario puede hard-delete su propia suscripción.

### 14.3 `notification_deliveries`

`id UUID PK`, `notification_id UUID NOT NULL FK notifications CASCADE`, `push_subscription_id UUID NOT NULL FK push_subscriptions CASCADE`, `status VARCHAR(16) NOT NULL DEFAULT 'PENDING'`, `attempt_count SMALLINT NOT NULL DEFAULT 0`, `next_attempt_at TIMESTAMPTZ NULL`, `delivered_at TIMESTAMPTZ NULL`, `last_error_code VARCHAR(64) NULL`, `created_at TIMESTAMPTZ NOT NULL`, `updated_at TIMESTAMPTZ NOT NULL`.

- `UNIQUE (notification_id, push_subscription_id)`.
- estados `PENDING`, `DELIVERED`, `FAILED`, `CANCELLED`.
- intentos >= 0; DELIVERED exige timestamp.
- índice parcial `(status, next_attempt_at, id)` para entregas pendientes.
- no almacena cuerpos ni claves de suscripción.

## 15. Retiro de miembros y transferencia

Al retirar a Silvia:

- WorkspaceMember pasa a REMOVED; User y membresía histórica permanecen.
- Tasks, PendingItems, ProjectStages y sus historias pasadas conservan user_id.
- contenido futuro se bloquea y se reasigna o elimina según la elección; `Eliminar todo` opera por `(workspace_id, responsible_user_id, fecha/estado futuro)`.
- Participants de Activities futuras pasan a REMOVED y sus reminders se desactivan; Activities pasadas no cambian.
- si era Líder, los Projects futuros deben reasignarse o eliminarse según el flujo aprobado; el historial de actor permanece.
- no puede retirarse a `workspace.owner_user_id`.

Transferencia: lock Workspace, membresía de propietario actual y nueva persona en orden UUID; comprobar nueva membresía ACTIVE; update condicional de `owner_user_id` y `lock_version`; luego el propietario anterior puede quedar como Miembro o salir. El trigger diferible valida propiedad+membresía al commit.

## 16. Política de eliminación/lifecycle

| Entidad | Política V2 |
|---|---|
| User | DISABLED si tiene historia; hard delete solo registro nunca activado y sin referencias |
| Workspace | hard delete solo flujo administrativo explícito sin historia valiosa; normalmente conservar |
| WorkspaceMember | ACTIVE/LEFT/REMOVED; no hard delete después de uso |
| Invitation | conservar estado hasta retención; luego hard delete |
| Category | Active/Inactive; hard delete solo sin referencias |
| MasterTask/ActivityMaster | Active/Inactive; hard delete solo sin ocurrencias |
| Task | futura no resuelta puede hard-delete; resuelta histórica se conserva |
| PendingItem | Active/Inactive; conservar si tiene historia |
| Project | Active/Inactive; conservar si tiene Etapas/historia |
| ProjectStage | hard delete solo antes de seguimiento; después conservar |
| Activity | futura puede cancelarse; pasada se conserva; hard delete solo borrador sin participantes/historia |
| ActivityParticipant | VISIBLE/REMOVED; conservar |
| Histories/state events | append-only, sin edición/borrado operativo |
| Notification | hard delete por retención; no es auditoría |
| PushSubscription | desactivar al invalidarse; usuario puede eliminarla |
| Tokens/deliveries | hard delete por retención de seguridad/operación |

## 17. Locking optimista

Usan `lock_version`: User, Workspace, WorkspaceMember, Category, MasterTask, Task, PendingItem, Project, ProjectStage, ActivityMaster, Activity, ActivityParticipant, ActivityReminder y ReminderPreference.

No lo usan: eventos de estado, tokens de acción, GenerationBatch, historiales, UserReviewMetadata (updates de columna independientes), Notification y Delivery append/transition mediante updates condicionales.

Las mutaciones incluyen versión esperada, actualizan con `WHERE lock_version = :expected`, incrementan y devuelven 409 con aislamiento. Operaciones batch bloquean padres antes que hijos y ordenan UUIDs determinísticamente.

## 18. Índices por patrón de consulta

Además de los índices descritos por entidad:

- login: users.email.
- selector de Workspace: members `(user_id,status,workspace_id)`.
- asignaciones/Revisión: responsible + estado/progreso + fecha.
- calendario global: organizer y participants por usuario; Activities por rango.
- comparación: member visibility y Activities por usuario/rango.
- campana: unread parcial por recipient.
- scheduling: preferencias activas por hora, activity reminders y delivery retry.
- reportes: Workspace+Category+fecha y master+fecha.

No se añaden índices separados para columnas ya cubiertas como prefijo útil o por UNIQUE. Los índices de expresión/rango se validarán con `EXPLAIN` antes de implementación.

## 19. Estrategia de enums

Todos los enums cerrados V2 usan enum Python + `VARCHAR` + `CHECK`: AccountStatus, WorkspaceKind, MembershipStatus, CalendarVisibility, InvitationStatus, GenerationEntityType/Pattern, TaskResult, HistoryEventType, ActivityStatus, ParticipantCalendarStatus, ReminderType/ScheduleKind, NotificationType y DeliveryStatus.

NotificationType cubre los eventos aprobados: invitación/respuesta, retiro de miembro, transferencia de propiedad, asignación/reasignación de Tarea/Pendiente/Líder/Etapa, alta/modificación/cancelación/retiro de Activity y los cinco tipos de reminder. No incluye comentarios ni cambios rutinarios de avance.

Category/Master no son enums: son tablas maestras. `GLOBAL_ADMIN` es valor restringido nullable, no rol de Workspace. Nuevos valores requieren migración del CHECK y actualización coordinada de aplicación, pero no alteración de tipos PostgreSQL nativos.

## 20. Valores derivados versus almacenados

| Valor | Decisión | Fuente |
|---|---|---|
| Task state | DERIVED | result + planned_date + fecha local |
| Pending state | DERIVED | progress |
| Pending compliance/detail | DERIVED | planned_date, completion_date, progress, fecha local |
| Project planned date | DERIVED | máximo planned_date de Etapas |
| Project progress | DERIVED | suma ponderada de Etapas |
| Project state | DERIVED | progreso de Etapas |
| Project compliance/detail | DERIVED | Etapas/fecha derivada |
| Project completion date | DERIVED | fechas de Etapas cuando todas finalizan |
| Task Category | DERIVED | MasterTask.category_id actual |
| Master Activity Category | DERIVED | ActivityMaster.category_id actual |
| Activity master name | STORED SNAPSHOT | Activity.title al crear |
| Custom Activity Category | STORED | Activity.custom_category_id |
| Calendar availability | DERIVED | Activities + organizer/participants + privacy |
| Latest Pending/Stage comment | DERIVED | última historia pertinente |
| Workspace visible role | DERIVED | owner_user_id vs membership |

## 21. Transición V1 → V2

Se recomienda un reset controlado del esquema de aplicación mediante **una nueva revisión Alembic posterior al head**, sin editar migraciones existentes. Es preferible a una alteración incremental porque los datos V1 son descartables y casi todas las tablas cambian identidad, cardinalidad o historia.

La revisión futura deberá:

1. comprobar opt-in explícito de reset V2;
2. rechazar hosts/bases de producción y exigir nombre local/test allowlisted;
3. verificar que no existan datos V2 reales o exigir una confirmación técnica separada;
4. eliminar únicamente tablas/tipos de aplicación enumerados;
5. crear el esquema V2 completo con constraints e índices;
6. validar `base → head` y `V1 head → V2 head` en bases descartables;
7. declarar downgrade destructivo/no reconstructivo con claridad.

Es una excepción pre-uso-real de V2. Tras publicación, toda migración deberá preservar datos.

## 22. Amenazas de esquema y controles

- **IDOR/Workspace forjado:** todo lookup incluye workspace y las asignaciones usan FKs compuestas de membresía.
- **Responsable/Participante forjado:** constraint de membresía más validación ACTIVE bajo lock.
- **GLOBAL_ADMIN:** columna separada, única y nunca inferida de Workspace.
- **Invitaciones:** digest, expiración, estado único y rate limiting fuera del esquema.
- **Tokens:** solo digest; consumo condicional; respuestas neutrales.
- **Push:** endpoints/claves cifrados, hash de unicidad y acceso solo del propietario/service.
- **Notification payload:** JSON tipado/allowlisted, texto plano y sin secretos/HTML.
- **PII histórica:** User no se borra si está referenciado; autorización limita exposición.
- **Mass assignment:** schemas de escritura separados y `extra='forbid'`; IDs de scope vienen del contexto autorizado.
- **Cascadas:** Workspace puede poseer datos, pero User/Member no borran historia de negocio.
- **Enumeración:** 404/403 neutrales para recursos fuera de scope; índices no cambian esta política.

RLS puede evaluarse después como defensa en profundidad; este modelo no depende de RLS para ser íntegro.

## 23. Decisiones deliberadamente no incluidas

- rutas API y payloads concretos;
- proveedor de correo o push;
- algoritmo del scheduler;
- métricas finales de Inicio/Reportes;
- política temporal exacta de retención de notificaciones/tokens;
- RLS obligatorio.

Estas decisiones no cambian el modelo lógico principal o pertenecen a etapas posteriores.

## 24. Persistencia técnica de rate limiting

Stage 2.9 agrega `rate_limit_buckets` fuera del catálogo de entidades de
negocio. Usa una PK compuesta por `action VARCHAR(32)`, `dimension VARCHAR(16)`,
`key_digest BYTEA(32)` y `window_start TIMESTAMPTZ`; añade
`attempt_count INTEGER NOT NULL DEFAULT 1`, `expires_at TIMESTAMPTZ NOT NULL` e
índice por expiración. Checks exigen textos no vacíos, digest de 32 bytes,
contador positivo y expiración posterior al inicio.

No almacena identificadores sensibles en claro. La aplicación genera claves
pseudónimas con HMAC-SHA256 y una subclave separada derivada del secreto de
sesión, o con `RATE_LIMIT_HMAC_KEY` explícita. Las filas expiran y pueden
eliminarse oportunísticamente; no son fuente de auditoría permanente.
