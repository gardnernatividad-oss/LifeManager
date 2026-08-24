# Validación ofensiva de identidad V2

## Estado

Stage 2.12 completado. El gate ejercita conjuntamente la identidad y los controles de seguridad activos; no introduce nuevas funciones ni sustituye el gate final 2.13.

## Matriz ejecutada

| Clase | Ataques representativos | Resultado |
|---|---|---|
| Autenticación | email desconocido, password erróneo, estados inactivos, payload malformado/sobredimensionado, repetición | fallo neutral; rate limit antes de dominio |
| Autorización | acceso anónimo/usuario normal, rol cliente forjado, GLOBAL_ADMIN retirado o disabled | denegado por estado/rol persistido |
| CSRF/CORS | header/cookie ausente, diferente, previo, fabricado o oversized; Origin hostil; preflight credentialed | denegado; solo origins explícitos reciben permiso |
| Inputs | mass assignment plano/anidado, SQL/XSS-like, UUID inválido, controles Unicode y longitudes | 422 seguro o tratamiento literal |
| Tokens | propósito incorrecto, random, malformed, expirado, revocado, consumido, replay y concurrencia | fallo neutral; una sola transición válida |
| Sesión | firma/payload alterado, claims ausentes, expiry, type/sub inválido, JWT oversized y fijación | 401 neutral; login rota sesión/CSRF |
| Abuso | brute force/spraying por IP/email/IP+email, headers forwarded falsos, Turnstile ausente/inválido/replay | buckets canónicos; no side effects antes de validación |
| Exposición | errores 422/500, OpenAPI, Settings repr, source/bundle/storage y cookies | sin secreto ni diagnóstico interno |

## Evidencia principal

- Login usa el mismo error para cuenta desconocida, password incorrecto y estados no utilizables. La ruta desconocida ejecuta Argon2 contra un dummy hash, evitando una divergencia obvia.
- Los buckets PostgreSQL del limiter son atómicos y usan HMAC de identidades canonicalizadas. Forwarded headers solo cuentan detrás de proxies allowlisted.
- Turnstile se verifica server-side, después del rate limit y antes del service/email. Un objeto cliente que aparente éxito no sustituye la respuesta del proveedor.
- Registro y acciones administrativas rechazan IDs, roles, estado, ownership, hashes, digests, timestamps, metadata y objetos privilegiados anidados.
- GLOBAL_ADMIN no evita membership: las primitivas de Workspace exigen membresía ACTIVE. El admin global fixture no recibe membresía sobre Personal Workspaces ajenos.
- Verification y reset separan propósito, digest, expiry y terminal state. Resend/reissue revoca el token anterior; los tests concurrentes aceptan una sola operación.
- El reset con password inválido falla antes de consultar/consumir token. Reset exitoso cambia el hash y hace inválida la sesión anterior.
- Login reemplaza cookies preexistentes con JWT y CSRF frescos. El JWT nunca aparece en el body ni en storage JavaScript.
- SQLAlchemy enlaza inputs; cadenas SQL/HTML permitidas permanecen datos. React muestra texto hostil escapado y no crea nodos HTML.
- Errores de DB, limiter, provider y services se convierten en envelopes estables sin SQL, constraints, paths, URLs, passwords ni tokens.

## Superficie OpenAPI validada

La superficie activa contiene únicamente login, me, logout, registration requests, verification/resend, recovery/reset y account-request administration. No existe endpoint V2 de debug, configuración, token listing, generic User CRUD ni mutación de account events. Las respuestas no publican hashes, digests o configuración server-only.

## PostgreSQL y concurrencia

Los tests PostgreSQL están protegidos por `LIFEMANAGER_V2_TEST_DATABASE_URL`, hostname local y nombre allowlisted. Cubren input hostil como datos, verificación/reset double-use, reissue/revoke, aprobación concurrente y threshold race del limiter. Si la variable no existe, se omiten sin tocar la DB local compartida.

## Hallazgos

No se confirmó defecto CRITICAL, HIGH, MEDIUM o LOW nuevo en el código activo durante Stage 2.12. No fue necesaria remediación de aplicación.

## Riesgos diferidos

- CSP y security headers: Stage posterior de hardening; defensa en profundidad frente a XSS.
- Límites globales de body en proxy/ASGI: hardening de infraestructura; los DTOs actuales ya acotan campos costosos.
- Observabilidad estructurada/redaction: etapa operacional; actualmente no existen body dumps/logging sensible activo.
- Prueba PostgreSQL del gate requiere que CI o desarrollo configure una base local desechable allowlisted.
- La credencial PostgreSQL histórica identificada en Stage 2.2 sigue requiriendo evidencia manual/rotación antes de Stage 2.13.

## Resultado

Stage 2.12: **PASS / Completado**. No quedan hallazgos CRITICAL/HIGH abiertos atribuibles a este gate. Stage 2.13 continúa pendiente.
