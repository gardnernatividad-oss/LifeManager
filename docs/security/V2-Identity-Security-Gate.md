# Gate final de identidad y seguridad V2

## Decisión

Stage 2.13: **PASS — COMPLETADO**.

La implementación y las pruebas técnicas de Phase 2 pasan. `SEC-SECRET-001` queda **CERRADO por rotación/revocación**: el product owner confirmó que la credencial histórica correspondía al usuario PostgreSQL local `postgres`, cambió la contraseña local, actualizó la configuración local de LifeManager y verificó la nueva conexión mediante `SELECT 1`. La credencial histórica queda revocada sin asumir que nunca fue reutilizada.

La evidencia del repositorio conserva además que la URL histórica apuntaba a loopback, que el valor no está en el árbol actual y que no aparece en ninguna URL PostgreSQL remota/Neon encontrada en la historia. No se recuperó, imprimió ni probó la credencial histórica y no se contactó Neon ni producción.

La `SECRET_KEY` presente en el `.env` local es deliberadamente exclusiva de desarrollo. Esto es aceptable solo localmente. Producción debe proporcionar una `SECRET_KEY` fuerte, única y exclusiva del backend mediante la configuración segura del proveedor; es un requisito operacional de despliegue y no un hallazgo abierto de `SEC-SECRET-001`.

No se reescribió Git.

## Reconciliación de pendientes

### Bloqueantes

- Ninguno.

### No bloqueante / hardening posterior

- CSP y security headers completos.
- Límite global de body en proxy/ASGI además de límites DTO.
- Logging/observabilidad estructurada con redacción central.
- Secret scanning/push protection y supply-chain CI.
- Session/device management avanzado y controles de verticales futuras.

### Operacional / proveedores

- Configurar proveedor real de email.
- Configurar credenciales/site key productivas de Turnstile sin introducir secretos frontend.
- Revisar DNS/dominios, TLS, MFA, least privilege y stores de Cloudflare/Render/Neon/GitHub.
- Probar backup/restore y definir RPO/RTO antes de datos reales.

### Cerrado

- `SEC-SECRET-001` mediante rotación/revocación de la credencial PostgreSQL local histórica y verificación de la configuración sustituta.
- Estado/rol de cuenta, registro restringido, verificación, aprobación/rechazo y Personal Workspace.
- Recovery/reset, política 8–128 y Argon2id.
- Tokens 256-bit con SHA-256, propósito, expiry, revocación, single-use y locks.
- Sesión cookie HttpOnly, expiración, logout, invalidación por password, CSRF/Origin/CORS.
- Rate limiting PostgreSQL, HMAC e IP/proxy trust.
- Turnstile server-side en registro, recovery y verification resend.
- DTO forbid, bounds, mass assignment, SQLi/XSS y envelopes/respuestas seguras.
- Regresión ofensiva Stage 2.12 y gate PostgreSQL real Stage 2.13.

## Evidencia PostgreSQL

Se creó exclusivamente `lifemanager_v2_test` en el servidor loopback configurado. Se rechazó cualquier host no local y se verificó que el origen compartido era `lifemanager`, que nunca fue target.

- blank database → Alembic head `c3d172b18308`;
- lifecycle registration → verification → approval → ACTIVE → Personal Workspace → login → me → logout;
- verification/reset purpose, expiry, revoke, replay y concurrencia;
- reset invalida sesión anterior y preserva Workspace/estado;
- aprobación concurrente y rollback transaccional;
- limiter UPSERT/threshold concurrency y pseudonimización;
- hostile SQL input como datos;
- invariantes de User/Workspace/WorkspaceMember relevantes;
- downgrade `c3d172b18308` → `e4f5a6b7c8d9` → upgrade head.

Resultado: 47 pruebas PostgreSQL aprobadas. La base desechable fue eliminada al terminar; la base local compartida no fue modificada.

## Evidencia de controles

- Estados PENDING_EMAIL_VERIFICATION, PENDING_APPROVAL, REJECTED y DISABLED no obtienen acceso normal.
- GLOBAL_ADMIN se deriva de DB, requiere ACTIVE, pierde autoridad inmediatamente y no implica membership.
- Cookies productivas conservan HttpOnly/Secure/SameSite/Path/TTL; CSRF es legible pero no es credencial.
- JWT no aparece en JSON/storage y cookies preexistentes se rotan al login.
- Turnstile mantiene orden schema → limiter → verifier → dominio y falla cerrado.
- Las siete DTOs de escritura activas rechazan extras; respuestas/OpenAPI son allowlists.
- No hay SQL interpolado con request data, HTML sink activo, error interno expuesto ni cache PWA de API privada.
- La configuración product-like falla ante secretos débiles/ausentes, wildcard credentialed CORS, cookie insegura, Turnstile incompleto o reset remoto/no allowlisted.

## Hallazgos por severidad

- CRITICAL abierto: 0.
- HIGH abierto: 0.
- MEDIUM abierto de Phase 2: 0; hardening operacional posterior listado arriba.
- LOW abierto de Phase 2: 0.

## Alcance del cierre

El PASS significa que la foundation de identidad/seguridad está completa; no que toda la aplicación, infraestructura o proveedores estén endurecidos definitivamente. Stage 2.13 queda **Completado** sin bloqueantes CRITICAL/HIGH abiertos. Los requisitos operacionales y el hardening posterior permanecen explícitamente fuera de este cierre.
