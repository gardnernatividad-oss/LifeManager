# Contrato API objetivo de LifeManager V2.0.0

## Stage 5.1

La API V2 expone `POST/GET /api/v2/workspaces/{workspace_id}/tasks`,
`GET/PATCH/DELETE /api/v2/workspaces/{workspace_id}/tasks/{task_id}` y las
acciones `complete` y `not-complete`. Los cuerpos son estrictos: el alcance,
actor, procedencia, resultado y timestamps se derivan en servidor. Las
mutaciones condicionales usan `lock_version`; los conflictos devuelven 409 y
las referencias externas al Workspace se ocultan con 404. La lista admite
paginación y filtros acotados por fecha, Responsable, Tarea, Categoría y
resultado. `generation_batch_id` permanece nulo para creación puntual y no se
expone en los DTO.

`PATCH` solo admite una Tarea puntual no resuelta cuya `planned_date` sea
posterior a la fecha local actual de la cuenta. Cuando la fecha llega, la Tarea
es Pendiente y ya no puede reprogramarse, reasignarse ni cambiar de entrada de
catálogo; únicamente su Responsable actual puede resolverla. Una Tarea
Programada futura no admite resolución anticipada. Las proyecciones
`can_edit` y `can_delete` reflejan esta regla, pero el backend la revalida bajo
bloqueo como autoridad final.

## Stage 4.1

Los catálogos de Categorías, Tareas y Actividades están disponibles bajo `/api/v2/workspaces/{workspace_id}`. Exponen listado, creación, lectura, actualización y operaciones dedicadas de activación/desactivación. Los DTO son estrictos, el servidor deriva normalización y alcance, y toda mutación exige `lock_version`. Stage 4.2 añadió hard delete únicamente para registros sin referencias, revalidado por servidor y protegido por FK `RESTRICT`.

## Stage 4.2

Las lecturas de gestión exponen `can_delete`, calculado por servidor. DELETE exige la versión esperada y solo elimina filas sin referencias; un FK retenido o una carrera devuelve 409. Los selectores mínimos `/selectors/categories`, `/selectors/tasks` y `/selectors/activities` devuelven activos por defecto y aceptan `current_id` para conservar visible un valor inactivo ya referenciado.

## Stage 4.3

El gate de Tablas maestras queda cerrado. Toda membership `ACTIVE` puede
administrar catálogos de su Workspace `ACTIVE`; LEFT, REMOVED, no miembros,
cuentas DISABLED y `GLOBAL_ADMIN` sin membership no obtienen acceso. La
reclasificación histórica usa siempre la Categoría actual del maestro, sin
snapshot. El inventario, la matriz y la evidencia están en
[`V2-Master-Table-Gate.md`](../security/V2-Master-Table-Gate.md).

## Stage 3.7

Quedan implementados `GET /api/v2/workspaces`,
`GET /api/v2/workspaces/management` y
`POST /api/v2/workspaces/{workspace_id}/reactivate`, además de la integración
frontend de creación, invitaciones, miembros, transferencia y lifecycle. Las
notas antiguas que difieran listado, selector o reactivación quedan
sustituidas por este estado.

El gate de Workspace está cerrado: 17 operaciones OpenAPI activas, sin rutas
duplicadas ni bypass `GLOBAL_ADMIN`. La matriz y evidencia están en
[`V2-Workspace-Gate.md`](../security/V2-Workspace-Gate.md).

## Estado y autoridad

**Implementación incremental.** Este documento es autoritativo para las convenciones transversales del API V2. Stage 2.8 implementa login, sesión cookie, CSRF, `/me`, logout e invalidación de sesiones sobre Stages 2.3–2.7; Stage 2.9 añade rate limiting compartido a las rutas de identidad protegidas. Stages 3.2–3.5 implementan creación Shared, invitaciones, membresías y lifecycle avanzado. Otras verticales continúan pendientes.

El comportamiento funcional proviene de [Functional-V2](../requirements/Functional-V2.md); layering, sesión y autorización provienen de [V2-Architecture-Baseline](../architecture/V2-Architecture-Baseline.md) y ADR-009–012. Las rutas `/api/v1` y sus payloads permanecen como contratos V1, no como plantilla V2.

## 1. Base y nomenclatura

Base canónica:

```text
/api/v2
```

- sustantivos plurales en minúsculas y kebab-case: `pending-items`, `master-tasks`, `activity-masters`;
- IDs UUID como segmentos: `/{resource_id}`;
- acciones no CRUD como subrecursos/verbos explícitos: `/transfer-ownership`, `/cancel`, `/mark-read`;
- no se codifica el nombre visible español en paths técnicos;
- una ruta no duplica scope en body ni usa trailing slash como contrato alternativo;
- GET es seguro/read-only; PUT reemplaza un recurso completo cuando corresponda; PATCH muta parcialmente; DELETE solo existe donde el dominio permite hard delete.

## 2. Familias globales

```text
/api/v2/auth/*
/api/v2/account/*
/api/v2/me
/api/v2/home
/api/v2/review/*
/api/v2/calendar/*
/api/v2/notifications/*
/api/v2/workspaces
/api/v2/admin/*
```

- Inicio, Revisión y Mi calendario derivan el conjunto de Workspaces desde memberships ACTIVE del usuario autenticado.
- Workspace discovery/creation y selector pertenecen a la familia global; las operaciones sobre un Workspace concreto usan su path scoped.
- Administration gestiona cuentas/plataforma. GLOBAL_ADMIN no obtiene acceso a contenido privado de Workspaces.
- Resultados globales incluyen `workspace_id` y representación mínima del Workspace cuando sea necesaria para contexto/deep link.

## 3. Recursos scoped

Patrón obligatorio:

```text
/api/v2/workspaces/{workspace_id}/<resource>
```

Familias: `tasks`, `pending-items`, `projects`, `categories`, `master-tasks`, `activity-masters`, `activities`, `reports/*`, `calendar/*`, `members/*`, `invitations/*` y `settings/*`.

`workspace_id` viene del path. Backend valida cuenta, membership ACTIVE y permiso requerido. Todo lookup combina `resource_id` con `workspace_id` en SQL. El selector frontend no es autoridad y no existe Workspace activo oculto en header, cookie, body o sesión.

Un miembro válido recibe el mismo 404 para un recurso inexistente o perteneciente a otro Workspace. Un usuario sin membership ACTIVE recibe 403. Las rutas globales nunca aceptan una lista de Workspaces aportada por el cliente para ampliar scope.

## 4. Autenticación y cuenta

Familias conceptuales obligatorias:

```text
POST /api/v2/auth/registration-requests
POST /api/v2/auth/email-verifications
POST /api/v2/auth/login
POST /api/v2/auth/logout
GET  /api/v2/me
POST /api/v2/auth/password-recovery-requests
POST /api/v2/auth/password-resets
GET  /api/v2/admin/account-requests
POST /api/v2/admin/account-requests/{user_id}/approve
POST /api/v2/admin/account-requests/{user_id}/reject
```

Implementado y validado en Stage 2.4:

```text
POST /api/v2/auth/registration-requests
GET  /api/v2/admin/account-requests
GET  /api/v2/admin/account-requests/{user_id}
POST /api/v2/admin/account-requests/{user_id}/approve
POST /api/v2/admin/account-requests/{user_id}/reject
```

Implementado y validado en Stage 2.5:

```text
POST /api/v2/auth/email-verifications
POST /api/v2/auth/email-verifications/resend
```

Implementado y validado en Stage 2.6:

```text
POST /api/v2/auth/password-recovery-requests
POST /api/v2/auth/password-resets
```

La solicitud acepta solo email, password, nombres y zona IANA; normaliza el email y responde siempre con un acuse neutral `202 {"accepted": true}` tanto para una solicitud nueva como para un email ya registrado. Crea `PENDING_EMAIL_VERIFICATION`, sin rol global, verificación, aprobación, Workspace ni membership. Stage 2.5 realizará mediante un servicio interno la transición auditada a `PENDING_APPROVAL`; no existe endpoint público para omitirla. La aprobación solo admite `PENDING_APPROVAL` y exige una cuenta ACTIVE con `GLOBAL_ADMIN` persistido. En una única transacción activa la cuenta, registra el evento, crea exactamente un Workspace `Personal` de tipo `PERSONAL` y la membership ACTIVE de su owner. Rechazar registra `REJECTED` sin crear Workspace.

La cola y el detalle de `/admin/account-requests` exponen únicamente cuentas `PENDING_APPROVAL` y una proyección administrativa mínima: identidad, timezone, estado, verificación y fecha de registro. No exponen hash, rol global, versiones internas, contenido de Workspace ni histories. Los duplicados concurrentes quedan limitados por `uq_users_email`; aprobaciones concurrentes se serializan con row lock y las constraints garantizan un único Personal Workspace/membership.

La neutralidad del cuerpo y estado HTTP reduce enumeración; Stage 2.9 añade rate limiting y Stage 2.10 verifica Turnstile después del límite y antes del trabajo de dominio. Stage 2.11 conserva la revisión temporal anti-enumeración. La autenticación administrativa sigue encapsulada en dependencies reutilizables y Stage 2.8 la transporta mediante la sesión cookie sin reescribir los services.

Cada registro persiste atómicamente un token `EMAIL_VERIFICATION` de 32 bytes aleatorios como digest SHA-256, nunca como token utilizable. Expira a las 24 horas, tiene purpose obligatorio y es de un solo uso. Verificarlo consume el token, invalida otros tokens activos y transiciona exclusivamente a `PENDING_APPROVAL`; no crea Workspace. El reenvío responde siempre `202 {"accepted": true}`, emite solo para cuentas elegibles y revoca cualquier token anterior antes de crear el nuevo.

La entrega usa una interfaz provider-neutral. El adapter predeterminado no envía externamente y existe un recorder aislado para desarrollo/tests. Proveedor, credencial y base URL pública quedan para configuración operativa posterior; la construcción de URL recibe la base explícitamente, contiene solo el token y nunca debe registrarse. Tokens consumidos, revocados o expirados podrán eliminarse mediante mantenimiento futuro; la auditoría de lifecycle permanece en `user_account_state_events`.

La recuperación acepta solo email y responde siempre `202 {"accepted": true}` sin revelar existencia ni estado. Únicamente una cuenta `ACTIVE` recibe realmente un token `PASSWORD_RESET`; `DISABLED` y estados pendientes/rechazados no son elegibles y el reset nunca cambia estado, rol ni Workspace. Cada solicitud revoca tokens reset anteriores y emite uno de 256 bits, digest SHA-256 y TTL de una hora. El reset acepta solo token y nueva contraseña, consume el token bajo lock, actualiza exclusivamente el hash Argon2 e invalida otros tokens reset activos.

Stage 2.7 aplica una única política a registro y reset: 8–128 caracteres exactos, al menos una letra mayúscula Unicode, una minúscula Unicode y un símbolo no alfanumérico/no whitespace. No exige dígito, no recorta ni normaliza el secreto y rechaza el exceso antes de Argon2. Un reset que falla la política no consulta ni consume el token, por lo que puede reintentarse. Stage 2.8 conectó el hook: cambiar el hash invalida las sesiones anteriores mediante su huella HMAC. Stage 2.9 limita recovery/reset por IP y recovery por email normalizado. Stage 2.10 exige Turnstile en la solicitud de recovery, pero no en el submit de reset.

No hay bootstrap automático de `GLOBAL_ADMIN`: la promoción inicial queda diferida a un procedimiento operativo explícito y auditado, sin credenciales ni identidad hard-coded. Registro aplica rate limit y luego Turnstile antes del orchestration service.

Los nombres finales de actions pueden concretarse sin cambiar la familia. Registro/recovery responden de forma neutral donde revelar existencia sea riesgoso. Verificación/reset reciben el token utilizable una sola vez; DB conserva solo digest.

`POST /api/v2/auth/login` emite una sesión de ocho horas en `lifemanager_v2_session`, cookie HttpOnly, Path `/`, SameSite explícito y Secure automático fuera de DB loopback. El JSON devuelve solo identidad segura. `GET /api/v2/me` restaura sesión y revalida cuenta ACTIVE, rol global y huella HMAC de la credencial contra DB. `POST /api/v2/auth/logout` elimina cookies. El frontend usa `credentials: include`; no recibe ni persiste JWT. Methods unsafe autenticados exigen `X-CSRF-Token`, cookie `lifemanager_v2_csrf` double-submit vinculada por digest HMAC al JWT y Origin permitido.

Errores 401 incluyen semántica de sesión inválida sin distinguir firma, expiración, cuenta inexistente o deshabilitada. Los endpoints admin exigen GLOBAL_ADMIN, que no implica membership privada.

### 4.1 Creación de Workspace Compartido

Stage 3.2 implementa:

```text
POST /api/v2/workspaces
```

Requiere sesión de una cuenta ACTIVE y la protección Origin/CSRF de toda
mutación autenticada. El request contiene únicamente `name`; el endpoint fija
`kind=SHARED` y deriva owner y membresía ACTIVE de la identidad autenticada. El
servicio hace flush sin commit y la ruta confirma una sola transacción. Responde
201 con `id`, `name` y `kind`. No permite crear Personal ni elegir owner, kind,
roles, estados, IDs, versiones, timestamps o relaciones. Nombres Shared
duplicados están permitidos.

Stage 3.3 implementa creación, listados accionables, aceptación, rechazo y
cancelación de invitaciones Shared para cuentas `ACTIVE` existentes. El
Stage 3.4 añade listado de miembros, retiro owner-only y salida voluntaria con
transiciones históricas `LEFT`/`REMOVED`. Stage 3.6 completó listado/selector y
la interfaz de administración. El contrato detallado está en
[`Workspaces.md`](Workspaces.md).

Stage 3.5 incorpora transferencia, desactivación, elegibilidad de hard delete y
resolución transaccional de responsabilidades futuras. `can_delete` nunca se
infiere en cliente. La gestión visual de Workspaces activos/inactivos y la
reactivación quedaron implementadas en Stage 3.6; Stage 3.7 validó la vertical
completa.

## 5. Envelope de error

```json
{
  "error": {
    "code": "TASK_VERSION_CONFLICT",
    "message": "La tarea cambió. Actualiza la información e inténtalo nuevamente.",
    "details": null,
    "request_id": "optional-correlation-id"
  }
}
```

- `code`: identificador técnico estable `UPPER_SNAKE_CASE`;
- `message`: mensaje español seguro y accionable;
- `details`: NULL salvo datos estructurados allowlisted;
- `request_id`: correlación opcional, nunca secreto.

Para 422, `details` puede ser una lista de `{field, code, message}` con paths de campos públicos. Nunca incluye valores sensibles.

| HTTP | Uso V2 |
|---:|---|
| 400 | request semánticamente inválido no cubierto por schema |
| 401 | sesión ausente/inválida o cuenta no usable |
| 403 | identidad válida sin permiso/membership requerido |
| 404 | recurso inexistente o fuera del Workspace de un miembro válido |
| 409 | lock conflict, lifecycle incompatible o unicidad de dominio esperada |
| 422 | validación estructural/de campos |
| 429 | rate limit/anti-abuse; puede incluir `Retry-After` |
| 500 | error inesperado con mensaje genérico y request ID |

No se devuelven stack traces, SQL, constraint names, tokens, secretos, hosts ni detalles que revelen recursos cross-Workspace.

### 5.1 Rate limiting de identidad

Stage 2.9 protege login, registro, verificación, reenvío, recovery, reset y
mutaciones administrativas mediante ventanas fijas compartidas en PostgreSQL.
Un exceso devuelve `429 RATE_LIMITED`, mensaje español seguro y `Retry-After`
entero calculado con la mayor espera de los buckets excedidos. Una falla del
almacenamiento compartido devuelve `503 SECURITY_CONTROL_UNAVAILABLE` antes de
ejecutar trabajo de identidad.

Los límites aprobados son: login IP 20/15 min, email 8/15 min e IP+email 5/15
min; registro IP 5/h y email 3/día; reenvío IP 10/h y email 3/h; submit de
verificación IP 20/15 min; recovery IP 10/h y email 3/h; reset IP 20/15 min;
approve/reject por actor admin 30/min. No se persisten tokens, IP ni emails en
claro. Las respuestas neutrales de registro/recovery no cambian.

### 5.2 Turnstile

`turnstile_token` es input público opcional en los DTO de registro, solicitud
de recovery y reenvío. Es opcional estructuralmente para permitir el modo
local/test explícitamente deshabilitado; cuando Turnstile está habilitado,
ausencia o challenge inválido produce `400 ANTI_BOT_VERIFICATION_FAILED`.
Falla de configuración/provider produce `503 SECURITY_CONTROL_UNAVAILABLE`.

El token se consume en la ruta después de rate limiting y antes de services,
DB o delivery. Nunca aparece en responses, logs, eventos ni persistencia.
Login, submit de verificación y submit de reset no incluyen este campo.

## 6. Paginación, filtros y orden

Listas paginadas usan `page` (default 1, mínimo 1) y `page_size` (default por recurso, rango 1–100).

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 25,
  "total_pages": 0
}
```

`total_pages=0` cuando `total=0`. Ordering usa `order_by` allowlisted por endpoint y `order_direction=asc|desc`; todo orden agrega `id` como desempate estable. No existe DSL genérico.

Filtros opcionales usan nombres de dominio: `category_id`, `responsible_user_id`, `is_active`, estados/resultados y fechas `<field>_from`/`<field>_until`, inclusivas para DATE salvo contrato explícito. IDs se validan UUID; filtros scoped no aceptan valores foreign Workspace como probes. Búsqueda textual es específica por recurso, normalizada y parametrizada.

## 7. Optimistic concurrency

Toda respuesta editable incluye `lock_version`. Una mutación envía `expected_lock_version` como campo obligatorio del action/update DTO; V2 inicial no usa ETag.

```text
GET → lock_version N
frontend edita
PATCH/action(expected_lock_version=N)
UPDATE ... WHERE id/scope AND lock_version=N
éxito → versión N+1
sin fila → 409 RESOURCE_VERSION_CONFLICT
```

El 409 no revela actor ni SQL. Frontend preserva input recuperable cuando sea seguro, descarta snapshots/versiones stale, refetch y muestra ConflictNotice. Operaciones batch validan todas las versiones antes de mutar y son atómicas.

## 8. Histories

PendingItemHistory y ProjectStageHistory son read-only desde API:

```text
GET /api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/history
GET /api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}/history
```

Orden canónico: `recorded_at DESC, id DESC`; soportan paginación común. Cada item expone progress, comment nullable, event type, timestamp y actor mínimo (`id`, display name según autorización). No existe POST/PATCH/DELETE genérico de history.

Tracking/correction actions mutan estado corriente e insertan history internamente. El cliente no aporta `actor_user_id`, `recorded_at` ni event type arbitrario. ProjectLeaderHistory y account-state events siguen el mismo principio y se leen solo en contextos autorizados.

## 9. Recurrencia finita

Stage 5.2 expone una acción explícita separada de la creación puntual:

`POST /api/v2/workspaces/{workspace_id}/tasks/recurring`

Acepta el siguiente contrato estricto:

```json
{
  "master_task_id": "uuid",
  "responsible_user_id": "uuid opcional en Personal",
  "recurrence": {
    "pattern": "DAILY | WEEKLY | MONTHLY",
    "date_from": "yyyy-mm-dd",
    "date_until": "yyyy-mm-dd",
    "weekdays": [0, 2, 4],
    "month_days": [1, 15, 31]
  }
}
```

- la ruta puntual existente conserva `planned_date` y no crea GenerationBatch;
- DAILY no admite arrays;
- WEEKLY exige weekdays únicos 0=Monday…6=Sunday y prohíbe month_days;
- MONTHLY exige month_days únicos 1–31 y prohíbe weekdays;
- `date_from <= date_until`; ambos son obligatorios;
- 29/30/31 cae al último día del mes sin cambiar el ancla;
- colisiones resultantes se deduplican antes de insertar;
- materialización es finita y atómica;
- una colisión con identidad ya persistida retorna 409 y revierte batch y ocurrencias;
- se admiten como máximo 1000 ocurrencias por solicitud;
- la respuesta contiene `created_count` e `items`, sin exponer el batch interno.

GenerationBatch conserva procedencia; no se expone como TaskSeries editable. `Solo esta` opera por occurrence ID. `Todas las futuras` es una action sobre occurrence/batch autorizado y no reescribe pasado.

Stage 5.3 concreta la mutación sin exponer el batch:

- `PATCH /api/v2/workspaces/{workspace_id}/tasks/{task_id}` acepta `scope=THIS|THIS_AND_FUTURE` dentro del DTO;
- `DELETE /api/v2/workspaces/{workspace_id}/tasks/{task_id}` acepta el mismo `scope` como query parameter;
- `THIS_AND_FUTURE` se rechaza en Tareas independientes;
- el alcance futuro permite cambiar `master_task_id` y/o `responsible_user_id`, pero no `planned_date` ni el patrón;
- la respuesta proyecta `is_generated` y capacidades `can_*_this/future`, sin `generation_batch_id`;
- el listado acepta `state=PROGRAMADA|PENDIENTE|COMPLETADA|NO_REALIZADA` y `generated=true|false`, además de sus filtros previos;
- toda operación es atómica, usa locking determinista por `planned_date,id` y retorna 409 ante versión o unicidad incompatible.

Stage 5.4 declara este contrato cerrado tras validar su superficie OpenAPI,
DTO ofensivo, aislamiento IDOR, capacidades derivadas, carreras significativas
y ciclo real en PostgreSQL desechable. No existe una ruta V1 de Tareas montada
en el runtime ni lookup de Tarea sin `workspace_id`. La evidencia autoritativa
está en `docs/security/V2-Task-Gate.md`.

Task usa DATE. Activity añade hora local y timezone IANA; backend rechaza horas DST inexistentes o ambiguas y retorna instantes UTC.

## 10. Activity y Calendar

Fronteras diferentes:

- Activity scoped: create/read/update/cancel, organizer-only mutations y participants;
- `/api/v2/calendar`: Mi calendario global;
- `/api/v2/workspaces/{workspace_id}/calendar`: vista colaborativa;
- availability comparison: intervalos autorizados;
- privacy preference: `WorkspaceMember.calendar_visibility`.

Una Activity compartida tiene una fila; participants son relaciones, no copias. No existe aceptar/rechazar invitación de Activity: WorkspaceInvitation es independiente.

- `SHOW_DETAILS`: puede retornar detalle autorizado;
- `AVAILABILITY_ONLY`: solo intervalos busy/free sin ID, título, categoría, participants ni deep link;
- `HIDE`: no retorna intervalos ni Activity subyacente.

Privacidad se aplica antes de serializar. La política cubre el calendario consolidado de la persona, no únicamente Activities nacidas en ese Workspace.

## 11. Notifications y Push

```text
GET  /api/v2/notifications
GET  /api/v2/notifications/unread-count
POST /api/v2/notifications/{notification_id}/mark-read
POST /api/v2/notifications/mark-all-read
GET  /api/v2/push-subscriptions
POST /api/v2/push-subscriptions
DELETE /api/v2/push-subscriptions/{subscription_id}
```

Las rutas concretas pueden usar PATCH para read state si mantienen semántica. Usuario solo ve/modifica sus notifications/subscriptions. Payload es mínimo, texto plano y deep link interno allowlisted. No hay notifications por comentarios ni cambios rutinarios de progreso. Una generación recurrente masiva produce como máximo una Notification lógica por destinatario/evento mediante dedup key.

Frontend registra/remueve subscriptions; backend cifra secretos, crea deliveries y envía Push. El API nunca devuelve endpoint/p256dh/auth completos innecesariamente.

## 12. Reminder preferences y jobs internos

Preferencias user-facing viven en `/api/v2/account/reminder-preferences` y ActivityReminder bajo la Activity correspondiente. Solo exponen tipos/patrones aprobados, timezone derivada y `lock_version` donde aplique.

Jobs internos usan un namespace no público, por ejemplo `/internal/jobs/reminders` y `/internal/jobs/notification-deliveries`. No usan cookie de usuario ni aparecen como rutas normales de producto. Requieren firma HMAC, timestamp, nonce/replay protection y allowlist operacional.

Cada job es retry-safe e idempotente, reclama trabajo atómicamente y responde solo métricas no sensibles. Scheduler secret nunca aparece en frontend, `VITE_*`, logs u OpenAPI público.

## 13. DTO y mass assignment

Pydantic v2 input DTOs usan `extra='forbid'`. Create/Update/Read/action schemas son separados. PATCH usa `exclude_unset`; null explícito solo si el dominio lo permite.

Siempre provienen de contexto confiable, no de body arbitrario:

- authenticated/current user y actor;
- `workspace_id` scoped;
- GLOBAL_ADMIN authority y membership/owner role;
- `created_by_user_id`, `resolved_by_user_id`, history actor y timestamps;
- Notification recipient/type cuando son derivados;
- Workspace owner durante aprovisionamiento/transferencia;
- GenerationBatch provenance y campos derivados;
- lock increment, estados derivados e IDs server-generated.

Assignment IDs sí pueden aparecer cuando el producto permite elegir Responsable/Líder/Participante, pero service valida membership ACTIVE y mismo Workspace bajo lock.

Stage 2.11 verificó las siete DTOs de escritura activas de identidad: todas rechazan extras. Email, nombres, timezone, passwords y tokens tienen límites autoritativos antes de hashing, JWT, Turnstile o consultas. El envelope 422 nunca incluye el valor `input`; los cuerpos malformados/form/text fallan sin reflejar datos. Las respuestas activas son allowlists y una regresión OpenAPI impide publicar hashes, digests o session internals. El detalle de controles y diferimientos está en `docs/security/V2-Input-and-Output-Security.md`.

## 14. Pendientes — Stages 6.2 y 6.3

Además del detalle workspace-scoped, el contrato publica `GET
/api/v2/workspaces/{workspace_id}/pending-items/{pending_item_id}/history` y
extiende seguimiento/corrección con comentario opcional. Comentario-only usa
la misma operación de seguimiento y crea exactamente un evento. No existen
mutaciones directas del historial ni exposición de grafos ORM. Actor, tipo y
timestamp son server-side; las escrituras conservan `lock_version` y la
transacción pertenece a la ruta.

`GET /api/v2/workspaces/{workspace_id}/pending-items` admite filtros opcionales
`is_active`, `responsible_user_id`, `category_id`, `state`, `compliance`,
`planned_from`, `planned_to` y `search`, además de paginación. Los filtros se
componen en SQL, las referencias se validan dentro del Workspace y el orden es
estable: Vigencia activa primero, fecha planificada ascendente con nulos al
final e identificador como desempate. La proyección incluye nombres de Categoría
y Responsable sin consultas por fila.

Stage 6.4 confirma DTOs estrictos, ausencia de mutaciones directas de historia,
aislamiento por Workspace, optimistic locking en escrituras y transacciones
atómicas. Estado, Cumplimiento, Detalle y capacidades `can_*` son proyecciones
server-side y no forman parte de los contratos de escritura.

## 15. Proyectos — Stage 7.1

El contrato workspace-scoped publica creación, listado paginado, detalle,
edición y acciones explícitas de desactivación/reactivación bajo
`/api/v2/workspaces/{workspace_id}/projects`. Categoría y Líder se validan como
referencias activas del mismo Workspace; Personal deriva el Líder y Shared
permite elegir cualquier miembro activo. Todas las escrituras usan
`lock_version`, transacción en ruta y DTOs estrictos. No existe `DELETE`.
Avance, Estado, Cumplimiento, finalización y operaciones de Etapas no se
publican en Stage 7.1 y quedan para Stage 7.2.

Stage 7.2 publica `GET/POST .../projects/{project_id}/stages`, `GET/PATCH
.../stages/{stage_id}` y `POST .../stages/{stage_id}/progress`. Los DTOs de
escritura exigen las versiones del Project y de la Etapa cuando corresponde.
ProjectRead agrega `weights_complete`, `stage_count` y `total_weight`, además
de las proyecciones derivadas. Una configuración incompleta es legible pero no
falsifica avance o cumplimiento global definitivo.

## 16. Terminología

Paths, enums y modelos usan identificadores técnicos (`ProjectStage`, `MasterTask`, `ActivityMaster`, `WorkspaceMember`). Mensajes/labels visibles usan Etapa, Tarea, Actividad, Propietario y Miembro. Roles V1 `ADMIN`/`VIEWER` no forman parte del contrato Workspace V2; `GLOBAL_ADMIN` es rol separado de plataforma.

## 17. Decisiones aún operativas

No están pendientes las convenciones anteriores. Se definirán durante implementación/operación:

- DTOs y actions exactos de cada vertical;
- proveedor email y librería Push;
- expiraciones, rate limits, retention y page-size defaults concretos;
- dominio/proxy productivo final;
- catálogo cerrado final de NotificationType antes de su migration CHECK;
- revisión Alembic V2 generada y secretos de provider.
