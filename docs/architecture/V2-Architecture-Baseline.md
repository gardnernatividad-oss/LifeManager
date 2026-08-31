# Línea base de arquitectura técnica LifeManager V2.0.0

## Contexto Workspace frontend (Stage 3.6)

El cliente conserva solo un UUID de preferencia ordinaria, lo valida contra el
listado `ACTIVE` y usa Personal como fallback. Toda cache dependiente incluye
Workspace o se elimina al cambiar contexto. Inicio, Revisión y Mi calendario
mantienen estado global independiente.

## Estado y autoridad

Arquitectura aprobada para implementación futura. No describe capacidades ya implementadas ni autoriza cambios de código, infraestructura o base de datos.

Este documento traduce [Functional-V2](../requirements/Functional-V2.md), [ADR-007](../project/decisions/ADR-007-V2-Functional-Baseline.md), [ADR-008](../project/decisions/ADR-008-V2-Physical-Data-Model.md) y el [plan de transición V2](../database/V2-Transition-Implementation-Plan.md) en convenciones técnicas. Para comportamiento visible prevalece Functional-V2; para estructura persistente, ADR-008 y el modelo V2; para arquitectura de implementación, este documento y ADR-009–012.

## 1. Vista ejecutiva

LifeManager V2 mantiene React/PWA → FastAPI → SQLAlchemy → PostgreSQL. No adopta microservicios, CQRS, un bus distribuido ni un framework de repositorios genérico.

```text
React/PWA
  → API client y TanStack Query
  → FastAPI router/dependencies
  → application service (solo casos multi-dominio)
  → domain service
  → SQLAlchemy Session
  → PostgreSQL
```

Principios obligatorios:

- autorización y privacidad se deciden en backend;
- Workspace explícito en URL para recursos scoped;
- una sola transacción por request de escritura;
- services hacen query/add/delete/execute/flush, nunca commit/rollback;
- routers poseen commit/rollback y llaman orchestration services cuando un caso cruza dominios;
- constraints son el límite final frente a carreras;
- frontend usa TanStack Query para estado servidor y Context únicamente para sesión/selección local;
- historia y Notification lógica se escriben en la misma transacción que el cambio de dominio;
- procesos externos invocan jobs idempotentes del backend; nunca acceden directamente a Neon.

## 2. Backend: capas y límites transaccionales

### 2.1 Router

Responsable de HTTP: parsing, dependencies, response schema/status, una llamada de caso de uso, `commit` exactamente una vez en éxito de escritura, `rollback` en error y `refresh` solo cuando la respuesta necesita valores generados. No contiene reglas de dominio ni compone queries.

### 2.2 Dependencies

Resuelven sesión, usuario autenticado y requisitos estructurales reutilizables. Pueden resolver una membresía ACTIVE o exigir GLOBAL_ADMIN, pero no mutan dominio ni sustituyen el scope de las queries.

### 2.3 Domain service

Implementa reglas y persistencia de un dominio. Acepta `Session`, identidad/scope autorizados y DTOs internos; usa SQLAlchemy 2.x, locking y `flush`. No conoce FastAPI, cookies ni status HTTP. No hace commit/rollback.

### 2.4 Application/orchestration service

Es el estándar para operaciones multi-dominio: registro+Personal Workspace, transferencia de propiedad, retiro/reasignación, Review batch, generación, cancelación compartida y mutación+Notification. Coordina domain services sobre **la misma Session**, fija orden de locks y produce un resultado. Tampoco hace commit/rollback.

No se usa para envolver CRUD simple ni se crean repositorios genéricos. Las consultas SQL permanecen en services específicos.

### 2.5 Casos de lectura

Los query services pueden componer joins/agregaciones entre dominios para Inicio, Revisión, Calendario y Reportes. Son read-only: no flush, commit, rollback ni side effects.

## 3. Scope API global y por Workspace

La API V2 usa prefijo `/api/v2`. No existe Workspace activo oculto en sesión, header o cookie.

### 3.1 Rutas globales

```text
/api/v2/auth/*
/api/v2/me
/api/v2/home
/api/v2/review
/api/v2/calendar
/api/v2/notifications
/api/v2/account/*
/api/v2/admin/*
```

Inicio, Revisión y Mi calendario agregan exclusivamente Workspaces con membresía ACTIVE del usuario. Cada fila retornada conserva `workspace_id` cuando el cliente necesita contexto o deep link.

### 3.2 Rutas scoped

```text
/api/v2/workspaces/{workspace_id}/tasks
/api/v2/workspaces/{workspace_id}/pending-items
/api/v2/workspaces/{workspace_id}/projects
/api/v2/workspaces/{workspace_id}/categories
/api/v2/workspaces/{workspace_id}/master-tasks
/api/v2/workspaces/{workspace_id}/activity-masters
/api/v2/workspaces/{workspace_id}/reports/*
/api/v2/workspaces/{workspace_id}/calendar/*
/api/v2/workspaces/{workspace_id}/members/*
```

El ID en URL mejora bookmark/deep link, cache keys y pruebas. El backend siempre valida membresía; un valor frontend nunca concede acceso. Los IDs de Workspace no se duplican en body salvo que formen parte de una representación read-only.

## 4. Autorización reutilizable

### 4.1 Dependencies

- `CurrentUser`: autentica, carga User y exige cuenta ACTIVE.
- `GlobalAdmin`: deriva de CurrentUser y exige `global_role=GLOBAL_ADMIN`.
- `ActiveWorkspaceMembership`: recibe `workspace_id`, consulta `(workspace_id,user_id,status=ACTIVE)` y devuelve Workspace+Member.
- `WorkspaceOwner`: exige además `workspace.owner_user_id=current_user.id`.

Estas dependencies reducen repetición en routers. No cargan recursos de dominio ni conceden acceso global implícito.

### 4.2 Helpers/services de autorización

Funciones reutilizables validan assignment/participant eligibility bajo lock, ownership transfer y políticas particulares como organizer-only. Los domain services vuelven a incluir `workspace_id` en toda query de recurso; una dependency de membresía no elimina esa obligación.

### 4.3 Base de datos

FKs compuestas garantizan mismo Workspace; constraints/triggers protegen owner y cardinalidad. Services verifican ACTIVE y permisos temporales. Frontend solo oculta/deshabilita acciones por UX.

`GLOBAL_ADMIN` administra cuentas/plataforma. **No obtiene acceso implícito al contenido privado de ningún Workspace**, no bypassa membership ni puede usar endpoints scoped sin autorización ordinaria.

## 5. Lookup, IDOR y semántica HTTP

Todo service scoped acepta `workspace_id`; consulta recurso con `WHERE id=:id AND workspace_id=:workspace_id`. Nunca carga globalmente por UUID para comparar después.

- usuario no autenticado o sesión inválida: 401;
- usuario autenticado sin membresía ACTIVE al Workspace solicitado: 403, salvo endpoint cuyo threat model exija ocultar el propio Workspace;
- miembro válido con UUID de recurso inexistente o de otro Workspace: 404 idéntico;
- miembro sin permiso funcional sobre recurso existente: 403;
- GLOBAL_ADMIN sigue la misma regla para contenido privado;
- conflicto de versión/estado/unicidad esperada: 409;
- payload inválido: 422; regla de request semántica no conflictiva: 400.

Historias y reportes parten de un padre scoped; no exponen endpoints globales de evento por UUID.

## 6. Sesión y autenticación V2

Se reemplaza el access token persistido en `localStorage` por un **JWT de sesión de vida corta en cookie `HttpOnly`, `Secure`, con scope de path y SameSite configurado**. El frontend no puede leer el token. Cada request autenticado carga User y verifica `account_status=ACTIVE`, por lo que deshabilitar una cuenta surte efecto aunque el JWT no haya expirado.

V2 inicial no añade refresh token ni sesión persistida. La cookie expira a las ocho horas. Logout elimina las cookies del dispositivo actual. Cada JWT lleva una huella HMAC del hash Argon2 vigente: reset o cambio de contraseña modifica el hash e invalida inmediatamente todas las sesiones anteriores al verificarlas contra DB; DISABLED también bloquea cada request. No existe revocación individual server-side. Si se exigen sesiones largas o gestión por dispositivo, deberá diseñarse una entidad Session en otra ADR/migration, nunca localStorage.

Claims mínimos: `sub`, `iat`, `exp`, `type=session` y un identificador no sensible. No se confían rol, estado ni membership desde claims; se consultan en DB. Login y respuestas de recovery son neutrales, con rate limit y Turnstile según Functional-V2.

La SPA restaura sesión llamando `/api/v2/me`; no reconstruye autoridad desde el JWT. Deep links esperan restoration y luego continúan o redirigen a login preservando destino seguro interno.

## 7. CORS, cookies y CSRF

Las requests de cookie usan `credentials: include`. Backend configura origins exactos allowlisted, nunca `*`, `allow_credentials=true`, métodos/headers mínimos y HTTPS en producción.

Mientras Cloudflare Pages y Render sean sitios distintos, la cookie requiere `SameSite=None; Secure`. La arquitectura recomendada para producción es usar dominios propios relacionados o un proxy API same-site para reducir bloqueo de third-party cookies; local usa `localhost` coherente para frontend/backend, cookie sin Secure solo en development explícito.

Toda operación unsafe (`POST`, `PUT`, `PATCH`, `DELETE`) requiere token CSRF double-submit: valor aleatorio en cookie legible no sensible y header `X-CSRF-Token`, comparados en tiempo constante. El JWT incluye un digest del token CSRF para ligarlo a esa sesión sin revelar el secreto HttpOnly. También se valida `Origin`/`Referer` cuando exista. GET/HEAD son side-effect free. CORS no reemplaza CSRF.

## 8. Frontend: sesión y Workspace

`AuthContext` se conserva como coordinador pequeño de `user`, `isAuthenticated`, `isInitializing`, login/logout y restauración. Deja de contener `accessToken`. El User proviene de `/me` y expone account status/global role solo para UX; backend decide.

`WorkspaceContext` separado conserva `selectedWorkspaceId`, lista autorizada y setter. Persiste únicamente el ID en localStorage porque no es secreto ni autoridad. Tras restaurar sesión, valida el ID contra Workspaces ACTIVE; si dejó de ser accesible, lo elimina y selecciona Personal o el primero autorizado. Logout limpia Context y caches.

Query keys scoped siempre incluyen Workspace: `['v2','workspaces',workspaceId,domain,params]`. Queries globales: `['v2','me']`, `['v2','home',params]`, `['v2','review',params]`, `['v2','calendar',params]`, `['v2','notifications',params]`. Cambiar selector no reescribe rutas globales ni actúa como autorización.

Calendario mantiene un selector interno (global/Workspace/personas) independiente del WorkspaceContext.

## 9. Routing frontend

```text
/login, /registro, /verificar-correo, /recuperar-contrasena
/inicio
/revision
/calendario
/notificaciones (opcional como ruta accesible además del overlay)
/configuracion/*
/administracion/*
/w/:workspaceId/tareas
/w/:workspaceId/pendientes
/w/:workspaceId/pendientes/:pendingItemId
/w/:workspaceId/proyectos
/w/:workspaceId/proyectos/:projectId
/w/:workspaceId/proyectos/:projectId/etapas/:stageId
/w/:workspaceId/tablas/*
/w/:workspaceId/reportes/*
/w/:workspaceId/calendario/*
```

El Workspace ID pertenece a URL para scoped pages. Guards esperan sesión, validan disponibilidad del Workspace y muestran acceso/no encontrado sin loops. Los deep links usan rutas internas allowlisted; nunca navegan a URL arbitraria del payload. Login conserva `location.pathname+search` solo si empieza con `/` y no `//`.

## 10. TanStack Query y cliente API

TanStack Query es la única fuente de server state. Context/local state solo guarda sesión derivada, selector, UI efímera y formularios dirty. No se añade Redux/Zustand.

- factories de query keys por dominio, con prefijos invalidables;
- filtros/paginación serializables y estables; el URL search params es preferido para vistas compartibles;
- invalidación estrecha después de mutaciones y actualización directa solo con respuesta canónica;
- sin optimistic update para datos con `lock_version`, batches, histories, ownership o privacidad;
- optimistic UI solo para acciones reversibles de bajo riesgo como read/unread, con rollback local;
- 409 limpia snapshots/versiones stale, preserva input recuperable cuando sea seguro, refetch y muestra `ConflictNotice`;
- campana usa query de unread y polling moderado al estar visible; no exige WebSocket en V2.

Un `api/client.ts` compartido configura base URL pública, credentials, CSRF header, timeout y normalización. Cada dominio tiene `<domain>Api.ts`; tipos DTO viven en `types/api/<domain>.ts` o junto al módulo si exclusivos. Se mantienen clientes manuscritos porque el tamaño V2 no justifica codegen; OpenAPI se usa para contract checks y puede reevaluarse.

## 11. DTOs, validación y mass assignment

- schemas separados `Create`, `Update`, `Read`, `ListResponse` y actions explícitas;
- Pydantic v2 con `extra='forbid'` para cuerpos de escritura;
- IDs de scope/actor vienen de path/session, nunca del body;
- PATCH usa `exclude_unset`; null explícito solo donde el contrato lo permite;
- respuestas mínimas, sin hashes, tokens, normalized names, claves push ni campos internos;
- enums API usan valores técnicos estables; frontend traduce etiquetas;
- paginación común: `items,total,page,page_size,total_pages`;
- validación sintáctica en Pydantic, autorización y reglas con DB en service, constraints como frontera final.

## 12. Errores

Se crea una jerarquía mínima `ApplicationError` con `code`, status y mensaje público seguro; subclasses por familia (`NotFound`, `Forbidden`, `Conflict`, `Validation`). Domain services no importan FastAPI. Handlers globales traducen a:

```json
{"error":{"code":"TASK_VERSION_CONFLICT","message":"...","details":null}}
```

`details` solo contiene campos validados, nunca constraint names, SQL, stack o existencia privada. 422 conserva formato FastAPI o se normaliza coordinadamente. Logs registran código, request ID y stack interno para 5xx, con redacción. Routers no repiten mapas salvo casos protocolarios como `WWW-Authenticate`.

Frontend convierte Axios/network/API errors a `ApiError`; componentes consumen `code` y fallback español. No muestra `exception.message` crudo.

## 13. Concurrencia y checklist por escritura

1. autenticar y validar scope;
2. iniciar una sola Session/transaction del request;
3. resolver todos los IDs scoped antes de mutar;
4. bloquear padres antes que hijos y UUIDs en orden ascendente;
5. verificar `expected_lock_version` para entidades editables;
6. validar lote completo antes del primer UPDATE;
7. ejecutar updates/inserts/history/notifications;
8. incrementar versiones y `flush` en services;
9. dejar que constraints resuelvan la última carrera y traducir solo violations conocidas;
10. router hace un commit; ante error, un rollback;
11. respuesta/refetch usa estado confirmado.

`SELECT FOR UPDATE` se usa en transferencias, retiro/reasignación, histories, estructura Project/Stages, consumo de tokens, generación idempotente y claim de jobs. Reads no bloquean. Los batches son atómicos; no hay éxito parcial salvo contrato explícito futuro.

## 14. Historia inmutable

PendingItem/ProjectStage mantienen estado corriente para consultas y agregan history en la misma transacción. Cada evento captura actor, progreso, comentario opcional, tipo y `recorded_at` del servidor. Un cambio de progreso o comentario no vacío crea evento; no-op no crea historia. Correction es una operación autorizada explícita, no CRUD del evento.

ProjectLeaderHistory y UserAccountStateEvent siguen el mismo principio: insert-only, actor y transición/valor atribuidos. No existen endpoints genéricos update/delete de history. Lectura exige scope/autorización del padre; reportes no exponen datos privados de otros Workspaces.

## 15. Recurrencia y generación

Un módulo puro `app/domain/recurrence.py` calcula fechas locales finitas para DAILY/WEEKLY/MONTHLY, sin SQLAlchemy ni Task/Activity. Comparte calendar math, límites inclusivos, fallback mensual y deduplicación.

`task_generation_service` convierte fechas en Task DATE. `activity_generation_service` combina fechas+hora+timezone IANA, rechaza instantes DST ambiguos/inexistentes y produce UTC. Un application service valida membresías/masters, límite técnico configurable, crea GenerationBatch y occurrences en una transacción.

GenerationBatch es procedencia inmutable, no plantilla. Unicidad DB e identificación del request impiden duplicados concurrentes. `Solo esta` opera por occurrence; `Todas las futuras` selecciona batch+scope+futuro y bloquea determinísticamente. Notificaciones masivas usan un dedup key por operación/destinatario, no una por fila accidental.

## 16. Activity, Calendar y privacidad

Services separados:

- Activity CRUD y mutación/cancelación futura por cualquier miembro ACTIVE del mismo Workspace ACTIVE;
- participant lifecycle/visibility/reminder;
- generation de Activity;
- query service de Mi calendario global;
- query service scoped de Workspace Calendar;
- availability comparison service.

Una Activity es compartida: no se copia por participante. Calendar agrega Activities donde User sea organizer o participant VISIBLE, respetando pasado/futuro y status.

`GenerationBatch` permanece como procedencia inmutable. Las operaciones `THIS`
y `THIS_AND_FUTURE` parten de una ocurrencia, bloquean de forma determinista y
solo alcanzan ocurrencias `SCHEDULED` cuyo `starts_at` continúa en el futuro.
El scope futuro propaga hora/duración local, catálogo, Organizador y
Participantes sin reescribir fechas de calendario ni historia. En Personal la
eliminación es física; en Shared se conserva la fila como `CANCELLED`. Retirar
participación solo afecta al usuario actor y desactiva únicamente sus
recordatorios futuros.

Privacidad se aplica antes de serializar:

- `SHOW_DETAILS`: DTO autorizado con detalles mínimos necesarios;
- `AVAILABILITY_ONLY`: solo intervalos busy/free, sin Activity ID, título, categoría, participantes ni deep link;
- `HIDE`: no retorna intervalos ni objetos subyacentes.

Nunca se envían detalles ocultos para taparlos con CSS. Comparación cruza membresía ACTIVE y política de cada persona en ese Workspace.

## 17. Notifications, scheduler y reminders

### 17.1 Notification lógica

El application service llama un `notification_service` reutilizable en la misma transacción del cambio de dominio. Inserta Notification con tipo allowlisted, texto plano, payload mínimo y deep link interno. Dedup key impide duplicados lógicos en operaciones masivas. La campana consulta Notification/read_at.

Enviar push nunca ocurre dentro de la transacción del request. Notification funciona como outbox lógico: tras commit, el job crea/claim NotificationDelivery y envía por adaptador Web Push. Fallos de proveedor no revierten dominio.

### 17.2 Scheduler S/0

Cloudflare Worker Cron Trigger invoca por HTTPS endpoints internos de jobs en Render. No accede a Neon. La request incluye timestamp, nonce y firma HMAC con secreto compartido; backend valida ventana/replay y aplica rate limit. Render puede despertar con cold start; la consulta usa ventanas vencidas y no depende del minuto exacto.

Jobs consultan preferencias/reminders due usando timezone de User, reclaman filas mediante update condicional/`FOR UPDATE SKIP LOCKED`, generan Notifications con dedup keys deterministas y programan retries con backoff. Cada ejecución es idempotente y recupera ventanas omitidas. Los cinco grupos aprobados comparten infraestructura, no reglas de dominio.

## 18. Web Push

Frontend solicita permiso solo tras acción/contexto explicativo, registra service worker y envía subscription al backend autenticado. La clave VAPID pública puede ser pública; endpoint/p256dh/auth nunca se exponen a otros usuarios.

Backend cifra secretos de subscription, soporta múltiples dispositivos, envía mediante adapter y desactiva endpoints 404/410. Notification click abre únicamente deep link interno validado y enfoca/abre la PWA. Service worker muestra payload mínimo; datos sensibles se consultan después de autenticar.

## 19. Email provider-neutral

`EmailService` define `send_verification` y `send_password_reset`. El account application service crea token aleatorio, persiste digest/expiry y solicita un mensaje. Un adapter de proveedor renderiza template y envía; dominio no importa SDK.

En V2 inicial, el orchestration service devuelve una instrucción de entrega sin secreto persistente adicional; el router confirma primero la transacción y después llama al adapter síncrono. Si el proveedor falla, el token ya seguro permanece y la respuesta permite reintento neutral que revoca/reemplaza el token anterior. No se envía un enlace que apunte a datos sin commit ni se revierte dominio por un fallo remoto. Al existir job infrastructure, puede encolarse mediante un registro persistente dedicado aprobado posteriormente. Nunca se guarda el token utilizable ni se loguea la URL completa.

Stage 2.5 materializa esta frontera con una interfaz provider-neutral y un adapter sin entrega externa como default seguro. La selección de proveedor gratuito, credenciales y `PUBLIC_FRONTEND_BASE_URL` sigue siendo configuración operativa pendiente; ninguna base localhost queda embebida. El link builder recibe la base explícitamente y añade únicamente el token. Un cambio futuro de email deberá revocar todos los action tokens del email anterior antes de emitir uno nuevo.

Stage 2.6 amplía la misma interfaz para password reset y reutiliza `AccountActionToken` con purpose aislado. Stage 2.8 conecta su hook con la estrategia de huella de credencial: al persistirse el nuevo hash, cualquier JWT anterior deja de coincidir. El reset no cambia `account_status`; un security-event log persistente requerirá diseño posterior.

Stage 2.7 establece `app.core.password_policy` como frontera única para todo password nuevo: longitud 8–128, mayúscula/minúscula mediante semántica Unicode de Python y símbolo no alfanumérico/no whitespace. El valor se valida exactamente como fue enviado y no se recorta. `pwdlib` usa Argon2id v19 con defaults recomendados (`m=65536`, `t=3`, `p=4`) y sal aleatoria; no se usa pepper porque su custodia/rotación agrega un punto de pérdida total sin infraestructura de claves que lo justifique. `verify_and_update_password` es el punto futuro para rehash tras autenticación exitosa; su persistencia pertenece a Stage 2.8. No se impone historial, rotación periódica, dígito ni lista externa de contraseñas comprometidas. El screening común/HIBP queda como hardening futuro sujeto a privacidad, costo y operación.

## 20. Configuración y secretos

Backend environment secrets: `DATABASE_URL`, `SECRET_KEY`, clave de cifrado push, VAPID private key, email API secret, scheduler HMAC secret, Turnstile secret y origins. Viven en Render/secret manager y `.env` local ignorado.

Frontend build-time público: `VITE_API_BASE_URL`, Turnstile site key y VAPID public key. Todo `VITE_*` se considera visible. Provider dashboards guardan credenciales/rotación; DB guarda preferencias y ciphertext/digests, nunca claves maestras.

No se imprimen URLs de DB, JWT/cookies, tokens, email links, push secrets ni payloads sensibles.

## 21. Logs, salud y observabilidad

Logs JSON en stdout para Render: timestamp, level, environment, request_id, route template, method, status, duration, error code y actor IDs solo cuando sea necesario/permitido. Headers, cookies, bodies, query secrets y PII se redactan. Eventos de seguridad (login failures agregados, rate limit, cambios de cuenta/propiedad) son estructurados sin credenciales.

Middleware acepta/genera `X-Request-ID` validado y lo retorna. Excepciones 5xx incluyen stack solo en logs. No se adopta APM pago en S/0; logs de Render y métricas de proveedores bastan inicialmente.

- `/health`: liveness, sin DB, respuesta rápida;
- `/ready`: readiness, `SELECT 1` con timeout y estado de dependencias indispensables, sin detalles de conexión.

## 22. UI reutilizable y mobile-first

Componentes base: `Modal/Dialog`, `ConfirmationDialog`, `FilterBar`, `Pagination`, `EmptyState`, `LoadingState`, `ErrorState`, `ConflictNotice`, `ProgressBar`, `DetailHeader`, `WorkspaceSelector`, `NotificationOverlay`. Son accesibles, composables y sin reglas de dominio; pages/domain components aportan contenido y actions.

Mobile es variante estructural desde el inicio: cards/listas cuando una tabla obligaría scroll horizontal, datos secundarios en detalle, filtros compactos expandibles, dialogs full-width controlados, touch targets mínimos 44×44 px, foco atrapado/restaurado y Calendar en vista día por defecto. Desktop usa tablas cuando comparabilidad lo justifica. Progress incluye texto/ARIA, no solo color.

## 23. Retiro de legado

Cada vertical V2 incluye inventario de rutas, services, schemas, clients, types, query keys y tests V1 que reemplaza. Secuencia:

1. identificar consumidores activos/shared;
2. implementar contrato V2 y migrar consumidores;
3. demostrar cero imports/referencias del legado;
4. eliminar código/tests exclusivos del legado en el mismo stage o uno de cleanup inmediato;
5. conservar utilities realmente compartidas con tests;
6. ejecutar búsqueda global y build/test.

No se hace un borrado masivo anticipado que rompa V1 antes del cutover de modelo; tampoco se dejan módulos inalcanzables indefinidamente. Al cambiar el esquema V2, rutas V1 incompatibles quedan explícitamente desregistradas hasta su reemplazo.

## 24. Arquitectura de pruebas

| Capa | Propósito |
|---|---|
| metadata/model | tipos, constraints, relaciones, exports |
| service unit | reglas puras, DTO, orchestration y errores con mocks/fakes |
| router/API | dependencies, auth, status, schemas y transaction calls |
| PostgreSQL integration | SQL real, FKs/checks, locks, arrays, triggers, agregaciones |
| migration | base→head, V1→V2, guards, introspección |
| frontend component/page | UX, accessibility, cache, 409, responsive structure |
| multi-user authorization | owner/member/nonmember/admin, cross-Workspace, privacy |
| concurrency | dos sesiones reales, versiones, deadlocks/order, idempotencia |
| HTTP-real | FastAPI+PostgreSQL sin mock de service para flujos críticos |
| E2E/smoke | navegador, cookie/CSRF, deep links y journeys de publicación |

PostgreSQL real es obligatorio para composite FKs, partial indexes, triggers, `FOR UPDATE`, `SKIP LOCKED`, histories atómicas, generación concurrente y queries globales. HTTP real es obligatorio para auth cookie/CSRF/CORS, IDOR, Review, transfer/removal y privacidad Calendar. Mocks complementan, no sustituyen estas capas.

## 25. CI/CD y gates

PR pipeline:

1. documentación/link/UTF-8/diff checks;
2. backend compile/static checks y suite;
3. PostgreSQL service: migrations+integration+concurrency;
4. frontend typecheck, ESLint, tests y build/PWA;
5. contract/OpenAPI compatibility;
6. SCA/dependency audit y secret scan; SAST se incorpora antes del gate productivo;
7. E2E crítico en entorno efímero/staging.

No se despliega si falla un gate. Tras merge aprobado: migración Neon primero solo cuando backend es compatible, Render backend después, smoke/readiness, Cloudflare frontend al final. Para el reset excepcional V2 se usa base descartable/preproducción y ventana explícita; nunca auto-reset production. Rollback de aplicación no pretende revertir el reset irreversible.

## 26. Git, PR y checkpoints

`main` permanece estable. Se recomienda branch por stage/vertical, PR con alcance/documentación/tests, revisión del product owner para comportamiento y revisión técnica para integridad/seguridad. Codex no crea commit, tag ni push sin instrucción explícita.

Checkpoint de commit: objetivo completo, tests requeridos verdes, diff revisado, sin secretos/artefactos y documentación sincronizada. Migración y modelos relacionados deben revisarse juntos aunque puedan usar commits claros separados dentro del mismo PR.

## 27. Versionado

La fuente autoritativa futura será un archivo raíz `VERSION` con SemVer sin prefijo (`2.0.0`). Backend y frontend lo leen en build/runtime; no mantienen literales independientes. Release tag usa `v2.0.0` y debe coincidir. CI falla ante divergencia entre VERSION, metadata/OpenAPI/package publicada y tag de release.

Durante desarrollo se usa `2.0.0-dev.N` o metadata de commit generada por CI sin editar múltiples archivos. Esta convención se implementará en un stage posterior; el drift V1 `0.1.0` permanece hasta entonces.

## 28. Security-by-design

| Riesgo | Control arquitectónico |
|---|---|
| IDOR/cross-Workspace | path scope + query scoped + membership + composite FK |
| privilege escalation | dependencies backend; GLOBAL_ADMIN separado y sin bypass privado |
| XSS/token theft | JWT HttpOnly, CSP/escaping, payload texto plano |
| CSRF | double-submit + Origin + SameSite/HTTPS |
| mass assignment | DTOs separados, extra forbid, IDs desde contexto |
| SQL injection | SQLAlchemy parametrizado; allowlists para sort/DDL |
| secret leakage | boundary env, redacción, ningún secret en VITE |
| notification/calendar privacy | payload mínimo; filtering antes de serializar |
| push secrecy | cifrado, endpoint hash, acceso por propietario |
| recovery abuse | digest, expiry, single use, respuesta neutral, rate limit |
| brute force/bots | Turnstile, rate limit por IP/cuenta y logs agregados |

Riesgo residual explícito: una cookie JWT corta no ofrece revocación por dispositivo. Se acepta para V2 inicial S/0 con account lookup por request; si cambian requisitos de duración/revocación, se diseña Session persistida antes de ampliar expiración.

## 29. Rate limiting distribuido de identidad

Stage 2.9 usa ventanas fijas en PostgreSQL y UPSERT atómico para que todos los
workers compartan contadores. Cada enforcement abre una sesión/transacción
independiente: el intento queda contabilizado incluso si la transacción de la
ruta revierte. La aplicación confía por defecto solo en el peer TCP; procesa
el header reenviado configurado únicamente cuando el peer inmediato pertenece
a `RATE_LIMIT_TRUSTED_PROXY_CIDRS`. IP, email normalizado, combinación y actor
admin se convierten en digest HMAC; no se guardan valores crudos.

Fallos del almacén producen fail-closed antes del trabajo costoso. OPTIONS,
fallos CSRF previos y autorización admin fallida no consumen buckets. El
contador no se reinicia tras login correcto: toda tentativa dentro de la
ventana cuenta y no existe bloqueo permanente. Turnstile, defensa de botnets
distribuidas y límites en edge permanecen para Stage 2.10/hardening.

## 30. Turnstile y frontera anti-bot

Stage 2.10 exige Turnstile en registro, solicitud de recuperación y reenvío de
verificación. El orden es schema → rate limit → Turnstile → trabajo de dominio;
el rate limiter evita llamadas al provider para requests ya bloqueadas. Login
permanece sin CAPTCHA por los límites IP/email/IP+email y Argon2 dummy; los
submits de verificación y reset permanecen sin CAPTCHA porque usan secretos de
256 bits, single-use y rate limit IP. Un challenge adaptativo de login puede
evaluarse posteriormente sin introducir risk scoring ahora.

`AntiBotVerifier` separa la aplicación del adapter Cloudflare. La verificación
siteverify corre en el threadpool de las rutas síncronas mediante HTTP estándar,
timeout de cinco segundos y sin retry automático. Usa la IP producida por el
resolver confiable de Stage 2.9. Challenge inválido devuelve error anti-bot;
configuración, red o respuesta malformada fallan cerrado antes de persistencia,
token o email.

`TURNSTILE_SECRET_KEY` es backend-only. `VITE_TURNSTILE_SITE_KEY` es pública y
solo habilita el widget oficial. El response token es efímero, no se persiste,
no se registra y no entra al dominio. Local/test puede deshabilitar el control
explícitamente; una configuración con cookies Secure exige Turnstile habilitado
y secreto presente. La configuración productiva real de Cloudflare sigue
siendo operación de despliegue, no está instalada en el repositorio.

CSP futuro deberá permitir el script/frame de
`https://challenges.cloudflare.com` siguiendo la guía vigente del provider.

## 31. Frontera Workspace Personal/Shared

Stage 3.1 implementa `app.services.v2_workspace` como boundary reutilizable
para todo vertical V2. La resolución exige simultáneamente cuenta `ACTIVE`,
Workspace exacto y `WorkspaceMember.status='ACTIVE'`; un UUID inexistente o
ajeno produce el mismo resultado 404. La autoridad de Propietario se deriva
solo de `workspaces.owner_user_id`. `GLOBAL_ADMIN` no participa ni crea un
bypass de contenido privado.

Personal se aprovisiona exclusivamente durante aprobación global y queda
protegido contra miembros ajenos, fin de la membresía propietaria, delete,
transferencia y conversión ordinarios. Shared conserva owner+membresía ACTIVE
y Stage 3.2 implementa su creación mediante `POST /api/v2/workspaces`. El DTO
acepta solo el nombre; kind, owner y membership se derivan en servidor y el
router confirma una única transacción. Listado/selector, invitaciones,
administración de miembros, transferencia y lifecycle están implementados y
validados por el gate de Stage 3.7.
No se introdujo ningún rol Workspace persistido: Propietario/Miembro siguen
siendo derivados.

Stage 3.3 implementa invitaciones para cuentas `ACTIVE` existentes con vigencia
de 14 días. El owner Shared crea/cancela y el destinatario autenticado
acepta/rechaza. La aceptación es atómica, crea o reactiva la identidad histórica
de membresía y reinicia su privacidad a `HIDE`. El digest interno se conserva por
compatibilidad física, pero V2.0.0 no entrega tokens ni implementa email o
notificaciones en este flujo.

Stage 3.4 implementa listado y finalización ordinaria de membresías Shared sin
cambiar el esquema. El orden canónico de lock es Workspace y luego
WorkspaceMember. Salir produce `LEFT`; el retiro por owner produce `REMOVED`;
ambos fijan `ended_at`, incrementan `lock_version` y cortan acceso porque toda
frontera privada exige `ACTIVE`. No se borra historia ni se altera privacidad al
salir. Owner, Personal y `GLOBAL_ADMIN` no tienen caminos alternativos. Una
invitación nueva reactiva la misma fila y restablece `HIDE`. Stage 3.5 conserva
la responsabilidad de transferencia, eliminación Shared y contenido futuro.

Stage 3.5 implementa transferencia de propiedad, desactivación conservadora,
hard delete exclusivamente vacío y resolución atómica de responsabilidades
futuras. Workspace `INACTIVE` conserva todo el grafo y queda fuera de la
autorización operacional. La elegibilidad de borrado comprueba en base todos
los recursos funcionales e históricos; únicamente la membresía estructural del
owner no bloquea. Salida/retiro resuelve Tareas, Pendientes, liderazgo de
Proyectos y Etapas mediante reasignación o eliminación segura; participantes y
recordatorios de Activities futuras se retiran/desactivan, mientras organizer e
historia se preservan.

Stage 3.6 integra selector/contexto y gestión colaborativa frontend. Stage 3.7
cierra la matriz integral, IDOR, mass assignment, cache, concurrencia y
PostgreSQL. Todas las mutaciones de invitación usan el orden canónico
`Workspace → WorkspaceInvitation` para serializarse con desactivación y hard
delete. Véase `docs/security/V2-Workspace-Gate.md`.

## 32. Decisiones y límites

ADRs vinculadas:

- ADR-009: layering, transacciones y error/concurrency V2;
- ADR-010: sesión cookie HttpOnly y CSRF;
- ADR-011: scope API y autorización Workspace;
- ADR-012: Notification, cron, reminders, push y email boundaries.

No decidido por esta arquitectura porque no afecta el inicio de implementación: proveedor concreto de email, librería Web Push, valores de expiración/retención, dominio productivo final y plataforma CI concreta. Se resuelven mediante configuración o stages operativos, sin pedir decisiones de producto salvo impacto visible/costo.

## 33. Base de notificaciones implementada — Stage 12.1

Las preferencias se persisten por usuario y tipo con control optimista. El
scheduler es un servicio invocable, no un daemon ni parte del ciclo request, y
genera `NotificationJob` idempotentes mediante una clave lógica única. La
preferencia, el job y la futura entrega son responsabilidades separadas. Cada
entrega deberá revalidar elegibilidad inmediatamente antes de enviarse.

Las suscripciones Web Push admiten varios dispositivos por usuario. Endpoint y
claves se cifran en reposo, la identidad del endpoint se compara mediante un
digest y ningún secreto Push se serializa. El service worker solo admite texto
seguro y navegación interna. Stage 12.1 no configura VAPID, proveedor, worker
externo ni envío real; esas decisiones permanecen en 12.2–12.4.

Stage 12.2 incorpora un claim PostgreSQL con `FOR UPDATE SKIP LOCKED` y estado
`PROCESSING`. La garantía es una ocurrencia lógica e intentos controlados, no
exactly-once externo. `NotificationDelivery` conserva el resultado por
subscription: los éxitos no se repiten, los fallos transitorios pueden
reintentarse y los endpoints permanentemente inválidos se desactivan. El
transporte permanece inyectable; los tests nunca contactan proveedores Push.
No se promete exactly-once externo: una caída después de que el proveedor
acepta el Push pero antes del commit puede requerir reconciliación o repetición.

Los seguimientos semanales de Stage 12.3 usan un job por usuario y ocurrencia,
no por recurso. Sus contenidos son únicamente counts agregados calculados cerca
del delivery. Pendientes agrupa por responsabilidad y Proyectos por liderazgo,
con agregados SQL de Etapas para evitar N+1. Los jobs vacíos se cancelan antes
de crear Notification o delivery.

Stage 12.4 añade al scheduler la consulta batch de `ActivityReminder` sobre
occurrences ya materializadas. La dedupe incluye usuario, Activity e instante
del reminder, permitiendo que una reprogramación válida cree una identidad nueva
sin revivir la anterior. Los entry points internos finales son
`generate_scheduled_jobs(window_start, window_end)`, `claim_due_job_ids(now)` y
`deliver_job(job_id, now, transport)`. No existe endpoint público de worker.
