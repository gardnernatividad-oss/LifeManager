# Plan de transición e implementación del esquema LifeManager V2.0.0

## Estado y autoridad

Este documento convierte el modelo aprobado en [V2-Target-Data-Model.md](V2-Target-Data-Model.md) y [ADR-008](../project/decisions/ADR-008-V2-Physical-Data-Model.md) en un plan de implementación mecánico. Es autoritativo para la transición de base de datos, pero **no constituye una migración ejecutada ni describe un esquema ya implementado**.

Los datos V1 son descartables por decisión del producto. La transición definitiva será un reset destructivo controlado mediante una única revisión Alembic nueva después del head V1. Ninguna revisión existente se editará.

## 1. Baseline Alembic verificado

La cadena es lineal y tiene un solo head:

```text
<base>
  -> 30b0a8ec85aa  Create users table
  -> 813f6ce3a35b  create workspaces and workspace members
  -> 5ff19898899a  prepare users for authentication
  -> 6fc7f7599458  create tasks table
  -> 25776ea3a156  create categories table
  -> 85484c8a04b9  add category to tasks
  -> b3a41f2c9d70  create projects table
  -> c7d9e2a4f681  add project to tasks
  -> e5b8c1d3a902  finalize manual task contract
  -> f6c9d2e4b713  create task series table
  -> a7d0e3f5c824  link tasks to task series
  -> d4e8f1a2b3c4  create daily form definition
  -> e5f9a2b3c4d5  create daily form submissions
  -> f7a0b1c2d3e4  add workspace timezone
  -> 0a1b2c3d4e5f  create user settings
  -> 1b2c3d4e5f60  create workspace settings
  -> c2d3e4f5a6b7  reset disposable legacy schema and create V1 identity foundation
  -> d3e4f5a6b7c8  create V1 target domain (HEAD)
```

`c2d3e4f5a6b7` eliminó el esquema legado vacío y creó identidad, Workspaces, membresías y metadata de seguimiento. Su downgrade es deliberadamente irreversible. `d3e4f5a6b7c8` creó el dominio V1 actual y sí baja sus tablas de negocio. La futura revisión V2 tendrá `down_revision = "d3e4f5a6b7c8"` y un ID generado por Alembic en la etapa de implementación.

### 1.1 Forma física V1 en el head

Tablas de aplicación esperadas en `public`:

- `users`;
- `workspaces`;
- `workspace_members`;
- `workspace_tracking_metadata`;
- `categories`;
- `master_tasks`;
- `tasks`;
- `pending_items`;
- `projects`;
- `project_steps`.

Objeto de infraestructura que permanece: `alembic_version`. Tipo PostgreSQL propio vigente: `workspacerole`. No permanecen las tablas anteriores a `c2d3e4f5a6b7` ni sus tipos `dailyformanswertype`, `weekstartson`, `taskoutcome`, `taskseriesfrequency`, `taskstatus` o `taskpriority`.

`backend/alembic/env.py` obtiene `DATABASE_URL` de `app.db.session`, escapa `%`, importa `app.models` para registrar metadata y ejecuta migraciones online dentro de transacción. En modo offline configura el URL sin conexión. La metadata actual registra únicamente los diez modelos V1 enumerados.

## 2. Estrategia definitiva de transición

Se aprueba el **reset destructivo V2 controlado en una revisión nueva**. Frente a una mutación incremental, evita columnas de compatibilidad, backfills ficticios, renombres semánticamente engañosos y conservación de enums/relaciones V1 incompatibles. Es adecuado porque los datos V1 están autorizados como descartables y casi todas las identidades relacionales cambian.

Una migración incremental tendría más riesgo: mezclaría roles V1 con propiedad V2, `ProjectStep` con `ProjectStage`, metadata por Workspace con metadata por User y registros actuales sin responsables/membresías históricas válidas. No aporta valor de preservación.

La excepción destructiva termina al crear el esquema V2. Desde ese head, toda migración posterior debe ser preservadora.

## 3. Límite exacto del reset

### 3.1 Objetos que se eliminan explícitamente

En orden de dependencias, sin comodines ni `DROP SCHEMA`:

1. `project_steps`;
2. `projects`;
3. `pending_items`;
4. `tasks`;
5. `master_tasks`;
6. `categories`;
7. `workspace_tracking_metadata`;
8. `workspace_members`;
9. `workspaces`;
10. `users`;
11. tipo PostgreSQL `workspacerole` después de eliminar sus consumidores.

Cada `DROP TABLE` debe nombrar una tabla verificada y ejecutarse **sin `CASCADE`**. Cualquier dependencia inesperada debe abortar el reset. No se eliminan esquemas, extensiones, funciones ajenas, otras tablas ni tipos no allowlisted.

### 3.2 Objetos que permanecen

- `public.alembic_version`, que Alembic actualiza normalmente al finalizar la revisión;
- esquema `public`;
- extensiones PostgreSQL ya instaladas, salvo que una futura decisión explícita autorice otra cosa;
- roles, grants y configuración del servidor;
- cualquier objeto fuera de la allowlist, cuya presencia inesperada provoca rechazo en vez de borrado.

### 3.3 Objetos recreados y pérdida aceptada

La misma revisión crea las 25 tablas V2, funciones auxiliares de validación de arrays, trigger diferible del propietario, constraints e índices descritos en este plan. Se pierden intencionalmente todos los usuarios, credenciales, Workspaces, membresías, categorías, maestros, tareas, pendientes, proyectos, etapas y timestamps de revisión V1. No hay transformación ni backfill.

## 4. Salvaguardas obligatorias de la migración futura

La revisión debe fallar antes del primer DDL destructivo si cualquiera de estas condiciones no se cumple:

1. `LIFEMANAGER_ALLOW_DESTRUCTIVE_V2_RESET=1` está definido de forma explícita.
2. La revisión de entrada leída desde `alembic_version` es exactamente `d3e4f5a6b7c8`.
3. `current_schema()` es `public` y `current_database()` coincide con una allowlist configurable de bases locales/test; nunca basta una coincidencia por prefijo libre.
4. El host configurado y `inet_server_addr()` son locales/test. Se rechazan expresamente hosts conocidos de Neon/Render y sufijos como `.neon.tech`; una dirección NULL o no reconocida falla cerrada.
5. La variable independiente `LIFEMANAGER_ENVIRONMENT` pertenece a `{local,test,development}`; `production`, `staging` o ausencia se rechazan.
6. El conjunto de tablas de aplicación es exactamente la forma V1 esperada más `alembic_version`; cualquier tabla adicional o faltante aborta.
7. Para cada tabla se verifican columnas sentinela y constraints esenciales, no solo el nombre. Como mínimo: `users.hashed_password`, `workspaces.kind`, `workspace_members.role`, `tasks.master_task_id`, `pending_items.progress`, `projects.lock_version`, `project_steps.position` y PK de `workspace_tracking_metadata`.
8. Los únicos tipos propios allowlisted son los esperados. Un tipo extra o una dependencia no reconocida aborta.
9. Cada nombre a eliminar proviene de constantes literales revisadas; no se construye desde input ni introspección libre.

El reset debe ejecutarse en la transacción de Alembic/PostgreSQL. Primero valida toda la forma; después elimina en orden explícito; finalmente crea todo V2. Una excepción revierte el DDL transaccional. No se usa `DROP ... CASCADE`, SQL wildcard ni `DROP SCHEMA`.

El downgrade debe lanzar un `RuntimeError` claro: no puede reconstruir datos V1 ni V2. Para volver a un head anterior se recrea una base descartable desde cero. El mensaje debe mencionar el carácter irreversible y el procedimiento seguro.

Las variables de opt-in solo se documentarán en `.env.example` cuando se implemente la migración; nunca se habilitan por defecto ni en producción.

## 5. Mapa de entidades y archivos

Se adopta un modelo principal por archivo; entidades históricas o auxiliares estrechamente ligadas conservan archivo propio para evitar ciclos y hacer explícita su política.

| Orden | Entidad | Tabla | Archivo objetivo | Disposición V1 | Dependencias principales |
|---:|---|---|---|---|---|
| 1 | User | `users` | `app/models/user.py` | reescribir | BaseEntity, enums de cuenta |
| 2 | UserAccountStateEvent | `user_account_state_events` | `app/models/user_account_state_event.py` | nuevo | User |
| 3 | AccountActionToken | `account_action_tokens` | `app/models/account_action_token.py` | nuevo | User |
| 4 | Workspace | `workspaces` | `app/models/workspace.py` | reescribir | User |
| 5 | WorkspaceMember | `workspace_members` | `app/models/workspace_member.py` | reescribir | Workspace, User |
| 6 | WorkspaceInvitation | `workspace_invitations` | `app/models/workspace_invitation.py` | nuevo | Workspace, User, WorkspaceMember |
| 7 | Category | `categories` | `app/models/category.py` | reescribir | Workspace |
| 8 | MasterTask | `master_tasks` | `app/models/master_task.py` | reescribir | Workspace, Category |
| 9 | ActivityMaster | `activity_masters` | `app/models/activity_master.py` | nuevo | Workspace, Category |
| 10 | GenerationBatch | `generation_batches` | `app/models/generation_batch.py` | nuevo | Workspace, WorkspaceMember |
| 11 | Task | `tasks` | `app/models/task.py` | reescribir | MasterTask, Member, GenerationBatch |
| 12 | PendingItem | `pending_items` | `app/models/pending_item.py` | reescribir | Category, Member |
| 13 | PendingItemHistory | `pending_item_history` | `app/models/pending_item_history.py` | nuevo | PendingItem, Member |
| 14 | Project | `projects` | `app/models/project.py` | reescribir | Category, Member |
| 15 | ProjectLeaderHistory | `project_leader_history` | `app/models/project_leader_history.py` | nuevo | Project, Member |
| 16 | ProjectStage | `project_stages` | `app/models/project_stage.py` | reemplaza `project_step.py` | Project, Member |
| 17 | ProjectStageHistory | `project_stage_history` | `app/models/project_stage_history.py` | nuevo | ProjectStage, Member |
| 18 | Activity | `activities` | `app/models/activity.py` | nuevo | ActivityMaster, Category, Member, Batch |
| 19 | ActivityParticipant | `activity_participants` | `app/models/activity_participant.py` | nuevo | Activity, Member |
| 20 | ActivityReminder | `activity_reminders` | `app/models/activity_reminder.py` | nuevo | Activity, Member |
| 21 | UserReviewMetadata | `user_review_metadata` | `app/models/user_review_metadata.py` | reemplaza `workspace_tracking_metadata.py` | User |
| 22 | ReminderPreference | `reminder_preferences` | `app/models/reminder_preference.py` | nuevo | User |
| 23 | Notification | `notifications` | `app/models/notification.py` | nuevo | User, Workspace |
| 24 | PushSubscription | `push_subscriptions` | `app/models/push_subscription.py` | nuevo | User |
| 25 | NotificationDelivery | `notification_deliveries` | `app/models/notification_delivery.py` | nuevo | Notification, PushSubscription |

`app/models/__init__.py` importará todos los modelos para que Alembic vea metadata completa. `Base` y `BaseEntity` permanecen en `app/models/base.py`, ajustando typing si hace falta pero no su propósito.

## 6. Organización de enums y constantes

Los enums técnicos persistidos vivirán en `app/models/enums.py`, sin importar modelos. Serán `class X(str, Enum)` y sus `.value` serán valores técnicos en inglés/mayúsculas. Modelos, schemas y services podrán importarlos sin ciclos. Etiquetas españolas pertenecen al frontend/i18n, nunca al enum persistido.

| Enum | Valores persistidos |
|---|---|
| `AccountStatus` | `PENDING_EMAIL_VERIFICATION`, `PENDING_APPROVAL`, `ACTIVE`, `REJECTED`, `DISABLED` |
| `GlobalRole` | `GLOBAL_ADMIN` |
| `WorkspaceKind` | `PERSONAL`, `SHARED` |
| `MembershipStatus` | `ACTIVE`, `LEFT`, `REMOVED` |
| `CalendarVisibility` | `SHOW_DETAILS`, `AVAILABILITY_ONLY`, `HIDE` |
| `InvitationStatus` | `PENDING`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `CANCELLED` |
| `AccountActionTokenType` | `EMAIL_VERIFICATION`, `PASSWORD_RESET` |
| `GenerationEntityType` | `TASK`, `ACTIVITY` |
| `GenerationPattern` | `DAILY`, `WEEKLY`, `MONTHLY` |
| `TaskResult` | `COMPLETED`, `NOT_COMPLETED` |
| `HistoryEventType` | `TRACKING`, `CORRECTION` |
| `ActivityStatus` | `SCHEDULED`, `CANCELLED` |
| `ParticipantCalendarStatus` | `VISIBLE`, `REMOVED` |
| `ReminderType` | `DAILY_SUMMARY`, `DAILY_REVIEW`, `PENDING_FOLLOW_UP`, `PROJECT_FOLLOW_UP` |
| `ScheduleKind` | `DAILY`, `WEEKLY`, `MONTHLY` |
| `DeliveryStatus` | `PENDING`, `DELIVERED`, `FAILED`, `CANCELLED` |

`NotificationType` enumera únicamente eventos aprobados en el modelo V2; su lista exacta se congela al implementar notificaciones, antes de crear su CHECK. Los nombres de constraints y de columnas se mantienen como constantes de migración cuando sea útil, no como literales duplicados en services.

## 7. Relaciones, cascadas y borrado ORM

Regla general: `cascade="all, delete-orphan"` solo se usa en hijos puramente poseídos cuya eliminación física está permitida por el dominio. Historiales y actores no reciben cascada ORM desde User/Member. Las relaciones cuyo FK usa `ON DELETE CASCADE` llevan `passive_deletes=True` en el padre para delegar en PostgreSQL.

| Relación | FK / dirección | DB delete | ORM recomendado |
|---|---|---|---|
| User–Workspace propietario | `workspaces.owner_user_id → users.id` | RESTRICT | bidireccional, sin cascade |
| Workspace–Member | `workspace_members.workspace_id → workspaces.id` | CASCADE | bidireccional, `passive_deletes=True`; no delete-orphan operativo |
| User–Member | `workspace_members.user_id → users.id` | RESTRICT | bidireccional, sin cascade |
| Workspace–Invitation | `workspace_invitations.workspace_id` | CASCADE | bidireccional, `passive_deletes=True` |
| Workspace–dominio | `workspace_id` | CASCADE | bidireccional donde sea útil, `passive_deletes=True` |
| Category–masters/Pending/Project | FK compuesta | RESTRICT | bidireccional, sin cascade |
| MasterTask–Task | FK compuesta | RESTRICT | bidireccional, sin cascade |
| ActivityMaster–Activity | FK compuesta nullable | RESTRICT | bidireccional, sin cascade |
| GenerationBatch–ocurrencias | FK compuesta nullable | RESTRICT | lectura bidireccional, sin cascade |
| Project–Stage | FK compuesta | CASCADE | bidireccional; `passive_deletes=True`, borrado de estructura solo según service |
| Pending/Stage–History | FK compuesta | RESTRICT | bidireccional solo lectura; jamás delete-orphan |
| Project–LeaderHistory | FK compuesta | RESTRICT | historial sin cascade |
| Activity–Participant/Reminder | FK compuesta | CASCADE | bidireccional, `passive_deletes=True`; lifecycle normal actualiza estado |
| Notification–Delivery | FK simple | CASCADE | bidireccional, `passive_deletes=True` por retención |
| PushSubscription–Delivery | FK simple | CASCADE | bidireccional, `passive_deletes=True` por retención |

Los atributos `foreign_keys` y `primaryjoin` se declaran explícitamente en relaciones múltiples a User/Member (owner, creator, responsible, actor, leader, organizer, resolver) para evitar joins ambiguos.

## 8. Integridad de mismo Workspace

La DB exige `UNIQUE (workspace_id, user_id)` en `workspace_members` y `UNIQUE (id, workspace_id)` en padres referenciados en forma compuesta. Las asignaciones usan FK compuesta, nunca `user_id → users.id` aislado:

- Task: `(workspace_id, responsible_user_id)`, creador y resolvedor;
- PendingItem: responsable y creador;
- PendingItemHistory: actor;
- Project: líder y creador;
- ProjectLeaderHistory: líder y actor;
- ProjectStage: responsable;
- ProjectStageHistory: actor;
- Activity: organizador, creador y cancelador;
- ActivityParticipant/Reminder: usuario;
- GenerationBatch: creador;
- WorkspaceInvitation: invitador.

Las relaciones a Category, master, Project, Stage, Activity, Batch e historial también incluyen `workspace_id`. La DB garantiza pertenencia estructural; el service además exige membresía `ACTIVE`, autorización y locking. La FK permite referencias históricas a membresías LEFT/REMOVED; esa distinción temporal solo puede validarse en service.

## 9. Propiedad y Personal Workspace

`workspaces.owner_user_id` es la única autoridad. `WorkspaceMember` no guarda rol. Se implementan:

- FK `owner_user_id → users.id ON DELETE RESTRICT`;
- índice único parcial `uq_workspaces_personal_owner` sobre `(owner_user_id) WHERE kind='PERSONAL'`;
- constraint trigger PostgreSQL `ct_workspaces_owner_active_member`, `DEFERRABLE INITIALLY DEFERRED`, que al insertar/cambiar Workspace o al cambiar/eliminar la membresía del propietario comprueba una fila `(workspace_id, owner_user_id, status='ACTIVE')`;
- función trigger `lifemanager_check_workspace_owner_membership()` con `SECURITY INVOKER`, schema calificado y `search_path` seguro.

El trigger corre al final de la sentencia diferida/commit y permite insertar Workspace y membresía en cualquier orden dentro de una transacción. También impide terminar la membresía propietaria. La prueba PostgreSQL debe cubrir commit válido, commit sin membresía, membresía inactiva y transferencia atómica.

El service de aprovisionamiento bloquea User, exige estado usable/ACTIVE, crea exactamente un Workspace PERSONAL cuyo owner es ese User y crea su membresía ACTIVE. No se admiten miembros adicionales en un Personal Workspace. El índice garantiza «como máximo uno»; el flujo transaccional garantiza «exactamente uno» para toda cuenta usable. La transferencia de propiedad solo aplica a SHARED; PERSONAL no cambia de propietario ni se convierte implícitamente.

## 10. GenerationBatch y operaciones futuras

`generation_batches` registra una solicitud finita ya materializada. Campos de recurrencia y creador son inmutables; no tiene `updated_at`, `lock_version`, activación, extensión ni sincronización. `entity_type` distingue TASK/ACTIVITY y un trigger/service impide que una ocurrencia referencie un batch del otro tipo.

`Solo esta` opera sobre una occurrence por ID. `Todas las futuras` selecciona por `(generation_batch_id, workspace_id)` y fecha/instante no pasado, ordena determinísticamente y aplica la operación a cada occurrence con su `lock_version`; no edita el batch ni regenera historia. En Activity se usa `starts_at`; el batch conserva timezone para interpretar el calendario original. En Task se usa `planned_date` y timezone NULL.

En retiro de miembros, el mismo batch puede ayudar a agrupar ocurrencias, pero la operación autorizada se filtra ante todo por Workspace, usuario responsable/participante y futuro. Nunca se asume que todo el batch pertenece a una sola persona.

## 11. Algoritmo mensual

Entrada: días ancla únicos 1–31, `date_from`, `date_until`, y para Activity timezone IANA más hora local/duración aprobadas.

```text
assert date_from <= date_until
anchors = sorted(unique(month_days))
month = first day of month(date_from)
dates = empty ordered set
while month <= first day of month(date_until):
    last_day = calendar_last_day(month.year, month.month)
    for anchor in anchors:
        day = min(anchor, last_day)
        candidate = date(month.year, month.month, day)
        if date_from <= candidate <= date_until:
            add candidate to ordered set
    month = first day of next calendar month
return dates in ascending order
```

El fallback no cambia el ancla: 31 produce 28/29 en febrero y vuelve a 31 cuando exista. Si 29, 30 y 31 convergen en febrero, el conjunto deduplica antes de insertar. No se usan duraciones fijas de 30 días.

Para Task, cada fecha permanece DATE y no se convierte a UTC. Para Activity, cada fecha se combina con la hora local y timezone del batch; se resuelve mediante aritmética de calendario. Una hora inexistente o ambigua por DST se rechaza con validación explícita, no se elige silenciosamente. `starts_at`/`ends_at` se persisten UTC y ninguna occurrence sale del rango inclusivo local From/Until. La generación calcula todas las occurrences, valida un límite técnico configurable, crea Batch y occurrences en una transacción e incorpora idempotencia mediante constraints finales.

## 12. Escrituras atómicas e historia

### 12.1 PendingItem y ProjectStage

Patrón común:

1. validar autenticación y Workspace;
2. bloquear padres en orden UUID: Project antes de Stage; PendingItem no requiere otro padre mutable;
3. bloquear items objetivo por UUID ordenado con `FOR UPDATE`;
4. comprobar pertenencia, elegibilidad y `expected_lock_version` de todo el lote antes de cualquier UPDATE;
5. derivar nuevo progreso/completion_date y validar comentario;
6. si no cambió progreso y no hay comentario no vacío, rechazar/no-op sin historia según contrato de la operación;
7. actualizar estado corriente, incrementar versión e insertar exactamente un evento history por cambio/comentario;
8. `flush`; el router/use case exterior conserva commit/rollback.

Un conflicto aborta todo el batch; no hay éxito parcial. Locks siguen Project → ProjectStages y UUID ascendente. Histories son append-only y nunca se corrigen en sitio.

### 12.2 ProjectLeaderHistory

Crear Project inserta el primer evento de líder. Reasignar bloquea Project y membresías implicadas en UUID ascendente, valida miembro ACTIVE y versión, actualiza `leader_user_id`, incrementa versión e inserta evento con nuevo líder y actor en la misma transacción. Asignar el mismo líder es no-op y no crea evento.

## 13. Transición de metadata de Revisión

`WorkspaceTrackingMetadata` y `workspace_tracking_metadata.py` se eliminan en el reset. Se crea `UserReviewMetadata`/`user_review_metadata.py` con PK/FK `user_id`, tres timestamps nullable (`tasks_last_saved_at`, `pending_items_last_saved_at`, `project_stages_last_saved_at`) y `updated_at`.

No se migra timestamp V1. La fila se crea perezosamente en el primer guardado exitoso o durante aprovisionamiento, con timestamps NULL. Cada bloque actualiza solo su columna y `updated_at` dentro de su propia transacción; un bloque no implica revisión de los demás ni de otro usuario.

## 14. Checklist de índices

Los nombres siguientes son definitivos salvo límite técnico de PostgreSQL; no se crean índices redundantes con PK/UNIQUE.

| Nombre | Tabla | Columnas/predicado | Tipo | Consulta |
|---|---|---|---|---|
| `ix_users_email` | users | email | no único | login |
| `uq_users_global_admin` | users | global_role WHERE `GLOBAL_ADMIN` | único parcial | único admin global |
| `ix_user_state_events_user_created` | user_account_state_events | user_id, created_at DESC, id | no único | auditoría de cuenta |
| `ix_account_tokens_user_type_expires` | account_action_tokens | user_id, token_type, expires_at | no único | token vigente |
| `uq_account_tokens_active_user_type` | account_action_tokens | user_id, token_type WHERE no consumido/revocado | único parcial | un token activo |
| `uq_workspaces_personal_owner` | workspaces | owner_user_id WHERE kind=`PERSONAL` | único parcial | Personal único |
| `ix_workspaces_owner_kind_id` | workspaces | owner_user_id, kind, id | no único | Workspaces propios |
| `ix_workspace_members_user_status_workspace` | workspace_members | user_id, status, workspace_id | no único | selector global |
| `ix_workspace_members_workspace_status_user` | workspace_members | workspace_id, status, user_id | no único | administración/asignación |
| `uq_workspace_invitations_pending_email` | workspace_invitations | workspace_id, recipient_email WHERE PENDING | único parcial | invitación pendiente |
| `ix_workspace_invitations_recipient_status_created` | workspace_invitations | recipient_user_id, status, created_at DESC | no único | bandeja invitaciones |
| `ix_workspace_invitations_expires` | workspace_invitations | expires_at | no único | expiración |
| `ix_categories_workspace_active_name_id` | categories | workspace_id, is_active, normalized_name, id | no único | catálogo |
| `ix_master_tasks_workspace_active_category_name_id` | master_tasks | workspace_id, is_active, category_id, normalized_name, id | no único | selector Tareas |
| `ix_activity_masters_workspace_active_category_name_id` | activity_masters | workspace_id, is_active, category_id, normalized_name, id | no único | selector Actividad |
| `ix_generation_batches_workspace_type_created` | generation_batches | workspace_id, entity_type, created_at DESC | no único | grupos creados |
| `ix_tasks_responsible_result_date_workspace_id` | tasks | responsible_user_id, result, planned_date, workspace_id, id | no único | Revisión global |
| `ix_tasks_workspace_date_id` | tasks | workspace_id, planned_date DESC, id | no único | registro |
| `ix_tasks_workspace_master_date` | tasks | workspace_id, master_task_id, planned_date DESC | no único | reporte |
| `ix_tasks_batch_date_id` | tasks | generation_batch_id, planned_date, id WHERE batch no NULL | no único parcial | futuras del batch |
| `ix_pending_responsible_active_progress_date` | pending_items | responsible_user_id, is_active, progress, planned_date, workspace_id, id | no único | Revisión global |
| `ix_pending_workspace_active_date_id` | pending_items | workspace_id, is_active, planned_date, id | no único | registro |
| `ix_pending_workspace_category_date` | pending_items | workspace_id, category_id, planned_date | no único | filtro/reporte |
| `ix_pending_history_item_recorded_id` | pending_item_history | pending_item_id, recorded_at DESC, id | no único | historial/comentario |
| `ix_pending_history_workspace_recorded` | pending_item_history | workspace_id, recorded_at DESC | no único | reporte |
| `ix_projects_workspace_active_category_name_id` | projects | workspace_id, is_active, category_id, name, id | no único | registro |
| `ix_projects_leader_active_workspace_id` | projects | leader_user_id, is_active, workspace_id, id | no único | asignaciones |
| `ix_project_leader_history_project_recorded` | project_leader_history | project_id, recorded_at DESC, id | no único | líderes históricos |
| `ix_project_stages_project_position_id` | project_stages | project_id, position, id | no único | estructura |
| `ix_project_stages_responsible_progress_date` | project_stages | responsible_user_id, progress, planned_date, workspace_id, id | no único | Revisión global |
| `ix_project_stage_history_stage_recorded` | project_stage_history | project_stage_id, recorded_at DESC, id | no único | historial |
| `ix_project_stage_history_workspace_recorded` | project_stage_history | workspace_id, recorded_at DESC | no único | reporte |
| `ix_activities_workspace_starts_ends` | activities | workspace_id, starts_at, ends_at | no único | calendario por rango |
| `ix_activities_organizer_starts_id` | activities | organizer_user_id, starts_at, id | no único | calendario personal |
| `ix_activities_batch_starts_id` | activities | generation_batch_id, starts_at, id | no único | futuras del batch |
| `uq_activities_batch_starts` | activities | generation_batch_id, starts_at WHERE batch no NULL | único parcial | idempotencia |
| `ix_activity_participants_user_status_activity` | activity_participants | user_id, calendar_status, activity_id | no único | calendario participante |
| `ix_activity_reminders_schedule` | activity_reminders | is_enabled, last_scheduled_for, activity_id | no único | scheduling |
| `ix_reminder_preferences_enabled_type_time` | reminder_preferences | is_enabled, reminder_type, local_time | no único | barrido recordatorios |
| `uq_notifications_recipient_dedup` | notifications | recipient_user_id, dedup_key WHERE key no NULL | único parcial | deduplicación |
| `ix_notifications_unread_recipient_created` | notifications | recipient_user_id, created_at DESC, id WHERE unread | no único parcial | campana |
| `ix_notifications_recipient_created` | notifications | recipient_user_id, created_at DESC, id | no único | historial |
| `ix_push_subscriptions_user_active_id` | push_subscriptions | user_id, is_active, id | no único | dispositivos activos |
| `ix_notification_deliveries_pending` | notification_deliveries | status, next_attempt_at, id WHERE PENDING | no único parcial | reintentos |

GiST/btree_gist queda diferido hasta medir consultas de rango; el B-tree de Activities es obligatorio inicialmente.

## 15. Checklist de constraints

### 15.1 Unicidad y FKs estructurales

- `uq_users_email`, `uq_account_action_tokens_digest`, `uq_workspace_members_workspace_user`, `uq_workspace_members_id_workspace`, `uq_categories_workspace_normalized_name`, `uq_categories_id_workspace`, `uq_master_tasks_workspace_normalized_name`, `uq_master_tasks_id_workspace`, equivalentes para ActivityMaster, `uq_generation_batches_id_workspace`.
- `uq_tasks_workspace_master_date_responsible`, `uq_pending_items_id_workspace`, `uq_projects_id_workspace`, `uq_project_stages_project_position`, `uq_project_stages_id_workspace`, `uq_activity_participants_activity_user`, `uq_activity_reminders_activity_user`, `uq_reminder_preferences_user_type`, `uq_push_subscriptions_endpoint_hash`, `uq_notification_deliveries_notification_subscription`.
- Toda FK simple: `fk_<tabla>_<columna>`. Toda FK workspace-aware: `fk_<tabla>_<recurso>_workspace` o `fk_<tabla>_<actor>_membership`.
- Histories referencian `(entity_id, workspace_id)` y `(workspace_id, actor_user_id)`; no dependen de borrado de User.

### 15.2 Checks determinísticos

- `ck_users_account_status_valid`, `ck_users_global_role_valid`, `ck_users_verification_consistent`, `ck_users_lock_version_positive` y checks no-blank.
- `ck_account_tokens_type_valid`, `ck_account_tokens_expiry`, `ck_account_tokens_terminal_exclusive`.
- `ck_workspaces_kind_valid`, `ck_workspaces_name_not_blank`, `ck_workspaces_lock_version_positive`.
- `ck_workspace_members_status_valid`, `ck_workspace_members_lifecycle_consistent`, `ck_workspace_members_visibility_valid`, `ck_workspace_members_lock_version_positive`.
- `ck_workspace_invitations_status_valid`, `ck_workspace_invitations_response_consistent`, `ck_workspace_invitations_expiry`.
- Para Category/masters: nombre no vacío y versión positiva.
- `ck_generation_batches_entity_type_valid`, `ck_generation_batches_pattern_valid`, `ck_generation_batches_date_range`, `ck_generation_batches_recurrence_shape`, `ck_generation_batches_timezone_shape`, más helpers de arrays.
- `ck_tasks_result_valid`, `ck_tasks_resolution_consistent`, `ck_tasks_lock_version_positive`.
- Pending/Stage: nombre no vacío, progreso 0–100, completion consistente, versión positiva; Pending lifecycle de fecha; Stage position/peso.
- Histories: progreso 0–100, event type y comentario no blank cuando existe.
- `ck_activities_source_xor`, `ck_activities_time_range`, `ck_activities_status_valid`, `ck_activities_cancellation_consistent`, `ck_activities_lock_version_positive`.
- `ck_activity_participants_status_valid`, `ck_activity_participants_lifecycle_consistent`; reminder minutes no negativo.
- ReminderPreference: tipo, schedule, shape de arrays y versión.
- Notification: título/body no vacíos, expiración posterior a creación; Delivery status/intentos/entrega consistente.

### 15.3 Reglas no expresables por fila

- `ct_workspaces_owner_active_member`: trigger diferible descrito arriba.
- `ct_occurrence_batch_entity_type`: trigger que valida Task→TASK y Activity→ACTIVITY, o dos triggers específicos.
- suma de pesos de Stage = 100.00 al activar/guardar estructura: service bajo lock de Project, porque un CHECK de fila no puede verla.
- append-only: permisos de aplicación y tests prohíben UPDATE/DELETE; si el rol DB de aplicación se separa por operación, revocar esos privilegios. No se requiere trigger en la primera implementación.
- inmutabilidad de GenerationBatch: schemas/services sin update y pruebas; DB constraints preservan la forma.

## 16. Plan de pruebas de modelo

### 16.1 Pruebas puras de metadata

- presencia de 25 tablas y exports;
- tipos, nulabilidad, defaults y nombres de constraints/índices;
- enum Python coincide exactamente con cada CHECK;
- relaciones/back_populates, FKs compuestas, `ondelete`, `passive_deletes` y ausencia de cascadas históricas;
- unicidad de Task, participante, reminder y tokens;
- límites de progreso/peso/versión y consistencia de timestamps;
- forma de GenerationBatch por patrón/entity type;
- histories sin `updated_at`/lock y metadata de Review con tres timestamps.

### 16.2 Pruebas PostgreSQL de integración

- Personal Workspace duplicado falla; SHARED múltiple funciona;
- trigger de owner acepta provisionamiento/transferencia atómica y rechaza owner sin miembro ACTIVE;
- assignments cross-workspace fallan por FK, incluyendo actor/participante;
- Task duplicate key, participant/reminder duplicate y token activo duplicado fallan;
- checks de arrays, progreso, peso, completion, cancelación y expiración;
- Category/master referenciados no se borran; histories sobreviven a lifecycle de miembros/entidades;
- Workspace cascade elimina solo su dominio; User con historia queda restringido;
- helpers mensuales: 29/30/31, febrero bisiesto/no bisiesto, colisión deduplicada, límites inclusivos y DST de Activity;
- no se puede insertar batch/occurrence de entity type cruzado;
- ejecución concurrente de historial/leader change respeta lock y versión.

### 16.3 Pruebas de salvaguarda/reset

- opt-in ausente, environment inseguro, host/base no allowlisted, revisión incorrecta, tabla extra, tabla faltante, columna sentinela faltante y tipo extra: todos rechazan antes de DROP;
- allowlist exacta local V1 permite reset;
- downgrade emite error irreversible;
- introspección post-upgrade coincide con metadata y no deja `workspacerole`.

## 17. Plan de pruebas de migración

Se usan bases PostgreSQL efímeras con URLs creadas por fixture, nunca `DATABASE_URL` heredado sin validación:

1. **Vacía → head:** ejecutar toda la cadena histórica hasta `d3e4f5a6b7c8`; habilitar opt-in solo para la base efímera; aplicar reset V2; comparar tablas/constraints/índices con el contrato.
2. **Head V1 → head V2:** crear base, `upgrade d3e4f5a6b7c8`, insertar como máximo fixtures V1 descartables explícitamente aprobados, ejecutar V2 y verificar pérdida intencional y esquema completo.
3. **Entorno inseguro:** parametrizar producción/staging, host/base no allowlisted y opt-in ausente; confirmar excepción antes de cualquier DDL mediante inspección antes/después.
4. **Forma inesperada:** desde V1 agregar una tabla sentinel o quitar/alterar una columna en base efímera; confirmar rechazo y rollback íntegro.

Cada test registra solo nombres/revisiones, nunca credenciales. El fixture exige que nombre y host sean locales y destruye únicamente su base efímera conocida. No se prueba contra Neon.

## 18. Compatibilidad temporal y secuencia

Reescribir modelos y aplicar el reset hará incompatibles routers, services, schemas y frontend V1. No se intentará sostener V1 mediante columnas ficticias. Para reducir el estado intermedio:

1. congelar el head V1 `d3e4f5a6b7c8` y ejecutar baseline completo;
2. crear `app/models/enums.py` y todos los modelos V2 en una rama/etapa cohesiva, con exports y tests de metadata;
3. escribir la única migración reset V2, funciones/triggers y tests de salvaguarda/migración;
4. validar metadata versus PostgreSQL y cadena base→head/V1→V2;
5. deshabilitar o retirar explícitamente rutas V1 incompatibles antes de levantar el runtime sobre V2, evitando una API aparentemente funcional;
6. adaptar verticales en orden: identidad/cuenta → Workspace/membresía/invitación → catálogos → generación/Task → Pending/historia → Project/Stage/historia → Activity/calendario → Review/preferencias → notificaciones;
7. adaptar Inicio/Reportes y finalmente frontend sobre contratos V2;
8. ejecutar E2E y revisión de seguridad antes de cualquier despliegue.

El siguiente stage recomendado es **model layer V2 + enums + tests de metadata**, sin aplicar todavía el reset a una base compartida. La migración se crea inmediatamente después, en una etapa propia y atómica.

## 19. Disposición de modelos V1

| Archivo/clase V1 | Destino |
|---|---|
| `base.py` / Base, BaseEntity | conservar; ajustar solo convenciones V2 necesarias |
| `user.py` / User | reescribir |
| `workspace.py` / Workspace, WorkspaceKind | reescribir; enum se mueve a `enums.py` |
| `workspace_member.py` / WorkspaceMember, WorkspaceRole | reescribir; eliminar roles V1 y usar estado/privacidad |
| `category.py` / Category | reescribir |
| `master_task.py` / MasterTask | reescribir |
| `task.py` / Task, TaskResult | reescribir; enum centralizado |
| `pending_item.py` / PendingItem | reescribir y añadir history separado |
| `project.py` / Project | reescribir |
| `project_step.py` / ProjectStep | retirar y reemplazar por `project_stage.py` / ProjectStage |
| `workspace_tracking_metadata.py` | retirar y reemplazar por `user_review_metadata.py` |
| `app/models/__init__.py` | reescribir exports completos |

No existe `TaskSeries` en los modelos V1 activos y no se reintroduce. Los remnants históricos permanecen únicamente en migraciones inmutables previas; GenerationBatch no es su sucesor semántico editable.

## 20. Bloqueos y decisiones cerradas

No hay bloqueos de producto para implementar la transición. Antes de escribir la migración deben fijarse operacionalmente, sin cambiar el dominio:

- ID de revisión Alembic generado;
- nombres exactos de bases locales/test allowlisted en configuración de pruebas;
- catálogo completo de `NotificationType` aprobado por ADR-007;
- si PostgreSQL disponible admite y justifica `btree_gist`; el plan base no depende de él.

Ninguno de estos puntos deja abierta la estrategia de reset, el modelo o sus invariantes.
