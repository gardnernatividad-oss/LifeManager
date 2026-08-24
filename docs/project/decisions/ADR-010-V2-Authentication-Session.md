# ADR-010: Autenticación y sesión V2

## Estado

Aceptado e implementado en Stage 2.8.

## Fecha

2026-08-22

## Contexto

V1 persiste Bearer JWT en `localStorage`, exponiéndolo a exfiltración por XSS. V2 es una React SPA/PWA servida por Cloudflare Pages con FastAPI en Render y prioriza seguridad sin añadir todavía una entidad de sesiones no aprobada en el modelo físico.

## Decisión

- V2 usa JWT de sesión de vida corta en cookie `HttpOnly`, `Secure` y con SameSite explícito.
- La SPA usa `credentials: include`, restaura mediante `/api/v2/me` y nunca lee/persiste el JWT.
- Backend carga User en cada request y exige cuenta ACTIVE; roles/membresías no se confían desde claims.
- Requests unsafe requieren CSRF double-submit ligado por digest al JWT y validación de Origin.
- CORS usa origins exactos y credentials; nunca wildcard.
- Logout elimina la cookie. No hay refresh token ni sesión persistida en la primera implementación.
- La sesión expira a las ocho horas y usa los claims mínimos `sub`, `iat`, `exp`, `type=session`, huella de credencial y binding CSRF; no incluye email, rol, membresías ni datos de Workspace.
- Cada JWT lleva una huella HMAC del hash de contraseña vigente. Reset o cambio de contraseña invalida todas las sesiones anteriores al compararla con DB; no existe revocación individual por dispositivo.
- Producción debe preferir dominios relacionados o proxy same-site; si sigue cross-site, usa `SameSite=None; Secure` y valida compatibilidad real de navegador/PWA.

## Consecuencias

- Se elimina el secreto de `localStorage` y se soportan restauración/deep links.
- Cookies implican CSRF y configuración CORS más estricta.
- La sesión corta no permite revocación individual por dispositivo; logout elimina las cookies del navegador actual, mientras cambio de credencial y deshabilitación bloquean globalmente por consulta DB. Requisitos futuros de sesión larga/dispositivo exigirán una ADR y modelo Session.
- La migración frontend/backend debe ser coordinada; V1 Bearer no se mezcla silenciosamente con V2 cookie.
