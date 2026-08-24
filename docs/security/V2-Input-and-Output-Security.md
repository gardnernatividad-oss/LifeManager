# Seguridad de entradas y salidas V2

## Estado

Stage 2.11 completado. Este documento registra el límite de confianza y los controles implementados para las rutas V2 activas de identidad y administración. No sustituye el threat model ni anticipa DTOs de verticales futuras.

## Límite de confianza

Todo valor procedente del navegador, path, query string, JSON, cookies, headers, Turnstile, deep links o proveedores externos es no confiable hasta que el backend lo valida. La validación frontend es únicamente UX; Pydantic, las dependencias y los services constituyen la autoridad.

## DTOs y mass assignment

Las siete DTOs de escritura activas (`RegistrationRequestCreate`, `LoginRequest`, `EmailVerificationRequest`, `EmailVerificationResendRequest`, `PasswordRecoveryRequest`, `PasswordResetRequest` y `RejectAccountRequest`) usan `extra="forbid"`. Ninguna recibe un ORM como contrato de escritura.

IDs, actor, rol global, estado de cuenta, Workspace, membresías, hashes, digests, timestamps, metadata de aprobación y versiones internas son derivados por servidor o por path tipado. Los cuerpos con campos privilegiados desconocidos se rechazan con 422; no se ignoran silenciosamente.

## Límites y normalización

- email: `EmailStr`, máximo 255, trim y lowercase antes del uso consistente en registro, login, reenvío y recovery;
- password/new_password: 8–128 mediante la política común; nunca se recorta ni normaliza;
- nombres: máximo 100, espacios colapsados y controles Unicode `Cc` rechazados sin prohibir nombres internacionales;
- timezone: máximo 100, validación IANA y controles `Cc` rechazados;
- tokens de acción: 1–512, opacos, sin trim ni normalización;
- Turnstile: 1–2048 y opaco;
- motivo administrativo: máximo 500, controles `Cc` rechazados y espacios colapsados;
- JWT de sesión: máximo técnico 4096 antes del parser;
- CSRF cookie/header: máximo técnico 512 antes de comparación criptográfica.

Los payloads actuales son objetos planos y acotados. No se incorpora middleware genérico de profundidad/tamaño en esta etapa; cada nueva vertical deberá limitar listas, textos, rangos y paginación antes de trabajo costoso.

## SQL e inyección

Las rutas activas construyen consultas con expresiones SQLAlchemy y valores enlazados. No existe `execute()` con SQL string ni interpolación de request data. Los usos de `text()` del modelo V2 son defaults, CHECKs e índices parciales constantes definidos por la aplicación.

El UPSERT del rate limiter usa `postgresql.insert()`: action, dimension, HMAC digest, ventanas y expiración son valores enlazados. Ninguna entrada decide nombres de tabla, columna, constraint u ORDER BY. SQL de migraciones es inaccesible desde requests.

## Respuestas, errores y serialización

Las respuestas usan DTOs allowlisted. No exponen hashes, token digests, JWT, CSRF internals, HMAC, Turnstile secret, Settings, grafos ORM ni diagnósticos del proveedor. El handler 500 V2 devuelve únicamente `INTERNAL_ERROR` y un mensaje estable. El envelope 422 elimina el valor `input` y conserva solo ubicación, código y mensaje.

Settings oculta en su representación `DATABASE_URL`, `DB_PASSWORD`, `SECRET_KEY`, `RATE_LIMIT_HMAC_KEY` y `TURNSTILE_SECRET_KEY`. No existe endpoint de configuración. `/health` solo informa estado. `SQL_ECHO` es falso por defecto y una configuración productiva no debe activarlo.

## XSS y URLs

El backend conserva texto como texto y no lo convierte en HTML confiable. En el frontend activo no existen usos de `dangerouslySetInnerHTML`, `innerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`, renderers HTML ni URLs `javascript:`. React escapa nombres y mensajes interpolados.

Las URLs futuras de verificación/reset usan una base controlada por aplicación y percent-encoding del token. Turnstile carga exclusivamente el endpoint oficial fijo. No hay redirect externo controlado por usuario. CSP y security headers completos quedan deliberadamente para hardening posterior; siguen siendo defensa en profundidad, no sustituto de escaping.

## Cookies, headers y logging

JWT malformado, sobredimensionado, con algoritmo/firma/claims inválidos produce 401 neutral. CSRF exige Origin allowlisted, cookie/header presentes, límites baratos, igualdad constante y binding con sesión. La IP solo acepta forwarded headers desde proxies configurados y se canonicaliza antes del HMAC.

No hay `print`, traceback, body dump ni logging de credenciales en las rutas V2 activas. La integración de observabilidad futura debe aplicar redacción estructurada a passwords, tokens, cookies, Authorization, CSRF y secretos.

## Evidencia y pendientes

Las regresiones cubren mass assignment, redacción 422, content types inválidos, límites, controles Unicode, JWT sobredimensionado, repr de configuración, allowlist OpenAPI, texto HTML/SQL literal y consulta PostgreSQL opcional contra una base local allowlisted. CSP, security headers, límites de infraestructura para tamaño total del body y observabilidad estructurada permanecen diferidos.
