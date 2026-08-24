# Contrato API objetivo de LifeManager V2.0.0

## Estado y autoridad

**Implementación incremental.** Este documento es autoritativo para las convenciones transversales del API V2. Stage 2.6 implementa recuperación y reset de contraseña sobre la identidad, verificación y aprobación de Stages 2.3–2.5; sesión final y otras verticales continúan pendientes.

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

La neutralidad del cuerpo y estado HTTP reduce enumeración, pero las diferencias temporales entre email nuevo y existente requieren rate limiting y revisión anti-enumeración en Stages 2.9/2.11. Stage 2.10 insertará Turnstile en la ruta, antes de llamar a `create_registration_request`; no se añade un campo ficticio al DTO. La autenticación administrativa sigue encapsulada en dependencies reutilizables y temporalmente transporta Bearer hasta que Stage 2.8 sustituya la sesión sin reescribir los services.

Cada registro persiste atómicamente un token `EMAIL_VERIFICATION` de 32 bytes aleatorios como digest SHA-256, nunca como token utilizable. Expira a las 24 horas, tiene purpose obligatorio y es de un solo uso. Verificarlo consume el token, invalida otros tokens activos y transiciona exclusivamente a `PENDING_APPROVAL`; no crea Workspace. El reenvío responde siempre `202 {"accepted": true}`, emite solo para cuentas elegibles y revoca cualquier token anterior antes de crear el nuevo.

La entrega usa una interfaz provider-neutral. El adapter predeterminado no envía externamente y existe un recorder aislado para desarrollo/tests. Proveedor, credencial y base URL pública quedan para configuración operativa posterior; la construcción de URL recibe la base explícitamente, contiene solo el token y nunca debe registrarse. Tokens consumidos, revocados o expirados podrán eliminarse mediante mantenimiento futuro; la auditoría de lifecycle permanece en `user_account_state_events`.

La recuperación acepta solo email y responde siempre `202 {"accepted": true}` sin revelar existencia ni estado. Únicamente una cuenta `ACTIVE` recibe realmente un token `PASSWORD_RESET`; `DISABLED` y estados pendientes/rechazados no son elegibles y el reset nunca cambia estado, rol ni Workspace. Cada solicitud revoca tokens reset anteriores y emite uno de 256 bits, digest SHA-256 y TTL de una hora. El reset acepta solo token y nueva contraseña, consume el token bajo lock, actualiza exclusivamente el hash Argon2 e invalida otros tokens reset activos.

La política final de contraseña permanece en Stage 2.7; Stage 2.6 reutiliza la frontera actual sin introducir reglas temporales divergentes ni password history. La invalidación real de sesiones existentes permanece en Stage 2.8 mediante el hook explícito del servicio. Stage 2.9 deberá limitar recovery/reset por IP, email normalizado/endpoint y, para intentos de token, bucket derivado sin persistir el token crudo. Turnstile para recovery se evaluará en Stage 2.10 según evidencia de abuso.

No hay bootstrap automático de `GLOBAL_ADMIN`: la promoción inicial queda diferida a un procedimiento operativo explícito y auditado, sin credenciales ni identidad hard-coded. Registro recibirá rate limit en Stage 2.9 y Turnstile en Stage 2.10; ambos se insertarán antes de llamar al orchestration service actual.

Los nombres finales de actions pueden concretarse sin cambiar la familia. Registro/recovery responden de forma neutral donde revelar existencia sea riesgoso. Verificación/reset reciben el token utilizable una sola vez; DB conserva solo digest.

Login emite JWT corto en cookie HttpOnly. Frontend usa `credentials: include`; no recibe token en JSON ni lo persiste. Logout elimina cookie. `/me` devuelve identidad, estado y rol global mínimos. Methods unsafe exigen header `X-CSRF-Token`, cookie double-submit vinculada por digest al JWT y Origin permitido.

Errores 401 incluyen semántica de sesión inválida sin distinguir firma, expiración, cuenta inexistente o deshabilitada. Los endpoints admin exigen GLOBAL_ADMIN, que no implica membership privada.

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

Create/generation actions aceptan un objeto opcional:

```json
{
  "pattern": "NONE | DAILY | WEEKLY | MONTHLY",
  "from": "yyyy-mm-dd",
  "until": "yyyy-mm-dd",
  "weekdays": [0, 2, 4],
  "month_days": [1, 15, 31]
}
```

- NONE crea una sola occurrence y no crea GenerationBatch;
- DAILY no admite arrays;
- WEEKLY exige weekdays únicos 0=Monday…6=Sunday y prohíbe month_days;
- MONTHLY exige month_days únicos 1–31 y prohíbe weekdays;
- `from <= until`; ambos son obligatorios para recurrence;
- 29/30/31 cae al último día del mes sin cambiar el ancla;
- colisiones resultantes se deduplican antes de insertar;
- materialización es finita, atómica e idempotente;
- respuesta puede incluir `generation_batch_id`, count e IDs creados según vertical.

GenerationBatch conserva procedencia; no se expone como TaskSeries editable. `Solo esta` opera por occurrence ID. `Todas las futuras` es una action sobre occurrence/batch autorizado y no reescribe pasado.

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

## 14. Terminología

Paths, enums y modelos usan identificadores técnicos (`ProjectStage`, `MasterTask`, `ActivityMaster`, `WorkspaceMember`). Mensajes/labels visibles usan Etapa, Tarea, Actividad, Propietario y Miembro. Roles V1 `ADMIN`/`VIEWER` no forman parte del contrato Workspace V2; `GLOBAL_ADMIN` es rol separado de plataforma.

## 15. Decisiones aún operativas

No están pendientes las convenciones anteriores. Se definirán durante implementación/operación:

- DTOs y actions exactos de cada vertical;
- proveedor email y librería Push;
- expiraciones, rate limits, retention y page-size defaults concretos;
- dominio/proxy productivo final;
- catálogo cerrado final de NotificationType antes de su migration CHECK;
- revisión Alembic V2 generada y secretos de provider.
