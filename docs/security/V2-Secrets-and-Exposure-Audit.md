# Auditoría de secretos y exposición de LifeManager V2.0.0

## 1. Estado y alcance

Documento vigente desde Stage 2.2. La auditoría se realizó sobre la rama `v2/base-schema`, HEAD `7cc16d6fccb89740f229cb3c9a8c1dae18c40a04`, el árbol actual, todo el historial Git alcanzable localmente y un build frontend de producción generado y eliminado durante la validación.

No se imprimieron secretos, no se probaron credenciales, no se contactaron remotos ni bases de datos y no se modificó configuración de proveedores. Los resultados describen presencia y riesgo, no validez operativa.

## 2. Regla de manejo

Nunca se registran aquí valores de credenciales, cookies, tokens, URLs autenticadas o claves. Los hallazgos usan IDs estables y solo indican categoría, ubicación, alcance y acción. Toda credencial de aspecto real que haya entrado en Git se considera expuesta hasta demostrar rotación o carácter desechable y ausencia de reutilización.

## 3. Resultado ejecutivo

- Secretos de aspecto real en el árbol actual: **0**.
- Secretos de aspecto real encontrados solo en historia: **1 potencial cerrado por rotación/revocación** (`SEC-SECRET-001`).
- Claves privadas, tokens GitHub o Bearer literales en árbol/historia: **0**.
- Los demás matches de URLs autenticadas pertenecen a `.env.example` o tests y usan material explícitamente ficticio.
- El build frontend no contiene URLs PostgreSQL, claves privadas, secretos de servidor ni tokens literales.
- El service worker precachea solamente shell y assets estáticos; no configura cache runtime de API.
- V1 histórico conservaba el access token en `localStorage`; Stage 2.8 retiró esa arquitectura de los paths activos V2.
- No se encontró un secreto actual que active una condición de parada inmediata.

## 4. Hallazgos

| ID | Severidad | Estado | Evidencia | Alcance | Remediación | Etapa / verificación |
|---|---|---|---|---|---|---|
| `SEC-SECRET-001` | HIGH | CERRADO — ROTACIÓN/REVOCACIÓN | `backend/alembic.ini` en commit `9811036d528b6df9a965072a51893acea9d5b612`; retirado en `b677ba58bcb15477548d5938e78bf0e1426d7b2b` | URL PostgreSQL del usuario local `postgres`; alcanzable en historia, sin coincidencia en URL remota/Neon encontrada | contraseña local rotada, configuración local actualizada y conexión sustituta verificada con `SELECT 1`; valor anterior revocado | 2.13; confirmación/remediación manual del product owner sin probar el valor histórico |
| `SEC-FE-001` | HIGH | CERRADO PARA V2 ACTIVO EN STAGE 2.8 | cliente y `AuthContext` V2 | el antiguo token Bearer persistido en Web Storage era extraíble por XSS | sesión V2 en cookie HttpOnly/Secure/SameSite, CSRF ligado, sin storage/attachment/restoration Bearer | tests de transporte/contexto, build y scan sin usos activos |
| `SEC-IGNORE-001` | LOW | CERRADO | `.gitignore` no cubría formatos comunes de claves/credenciales | commit accidental futuro | añadidos ignores de PEM/KEY/P12/PFX y JSON de credenciales/service accounts | 2.2; `git check-ignore` y ningún tracked afectado |
| `SEC-CACHE-001` | LOW | CONTROL ACTUAL | `frontend/vite.config.ts`, build `dist/sw.js` temporal | cache PWA | mantener solo precache estático; prohibir runtime cache de API privada | 2.12; inspección de SW/build |
| `SEC-CONFIG-001` | MEDIUM | CERRADO PARA IDENTIDAD ACTIVA | Settings V2 cubre sesión, CSRF binding, limiter y Turnstile; secretos futuros aún no existen | futuros email/VAPID/scheduler secrets | añadir solo cuando se implementen sus módulos; setup productivo de Turnstile/email es operacional | 2.13 verificado; módulos posteriores |
| `SEC-LOG-001` | MEDIUM | CERRADO PARA V2 ACTIVO | envelope 422/500, `repr` de Settings y `SQL_ECHO=false`; sin body dumps/logging sensible | futura fuga al incorporar observabilidad | mantener redacción y añadir logging estructurado en hardening | 2.11–2.13 verificado |
| `SEC-API-001` | HIGH | CERRADO PARA IDENTIDAD ACTIVA | DTOs allowlist, `extra='forbid'`, OpenAPI y respuestas minimizadas | serialización accidental en verticales futuras | repetir pruebas exactas por vertical; nunca serializar ORM genérico | 2.11–2.13 verificado |
| `SEC-SC-001` | MEDIUM | DIFERIDO — HARDENING | no existe `.github/` ni automatización de secret scanning en repo | supply chain/push accidental | habilitar controles GitHub y evaluar gitleaks/detect-secrets en CI | hardening posterior; no bloquea foundation local |

## 5. Árbol actual y archivos de entorno

`.env`, `.env.*`, archivos SQLite y dumps están ignorados; `!.env.example` permite plantillas. Solo `backend/.env.example` y `frontend/.env.example` están tracked, con valores de ejemplo. No hay evidencia de `.env` real históricamente tracked.

Se añadieron ignores preventivos para `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials*.json` y `service-account*.json`. No existía ningún archivo tracked afectado. Los ignores reducen commits accidentales, pero no sustituyen secret scanning ni revisión.

## 6. Hallazgo PostgreSQL histórico

La revisión inicial `9811036d528b6df9a965072a51893acea9d5b612` incluyó una URL con componentes de usuario, contraseña, host y base en `backend/alembic.ini`. El hostname es de loopback/local según clasificación textual; no es un hostname remoto. La revisión `b677ba58bcb15477548d5938e78bf0e1426d7b2b` reemplazó el valor por configuración de entorno.

El archivo actual deja `sqlalchemy.url` vacío. `backend/alembic/env.py` obtiene la URL desde `app.db.session`, que a su vez exige `DATABASE_URL` o el conjunto completo de componentes DB en settings. No existe fallback hard-coded y Alembic no imprime explícitamente la URL. La configuración actual usa una fuente distinta: entorno protegido.

El valor permanece alcanzable en Git y el remote configurado apunta a GitHub; por prudencia se presume que la historia pudo ser publicada. Como no fue posible confirmar su no reutilización histórica, el product owner rotó la contraseña del usuario PostgreSQL local `postgres`, actualizó la configuración local y verificó la conexión sustituta con `SELECT 1`. El valor anterior queda revocado. No se intentó autenticar con el valor histórico.

### Decisión sobre historia

Decisión **A satisfecha**: la rotación/revocación se completó y no se reescribe historia ahora. Una eventual limpieza coordinada de historia es hardening posterior; no elimina copias existentes ni sustituye la revocación ya realizada.

## 7. Variables de entorno y ubicación aprobada

| Variable/capacidad | Clase | Ubicación permitida |
|---|---|---|
| `DATABASE_URL`, `DB_PASSWORD` | SECRET | Render secret/local `.env` ignorado; nunca frontend |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | operacional sensible | backend environment; no bundle |
| `SECRET_KEY` | SECRET | Render secret/local `.env`; mínimo actual de 32 caracteres |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM` | operacional no secreto | backend environment/config revisado |
| `SQL_ECHO` | operacional no secreto | `false` en producción |
| `CORS_ALLOWED_ORIGINS` | público/operacional | backend environment; allowlist exacta |
| `TASK_BULK_MAX_OCCURRENCES` | operacional no secreto | backend environment |
| CSRF signing/binding secret futuro | SECRET | backend secret store; no `VITE_*` |
| Turnstile site key futura | PÚBLICO | `VITE_*` permitido |
| Turnstile secret futuro | SECRET | backend/provider secret store |
| email/SMTP/API secret futuro | SECRET | backend/provider secret store |
| VAPID public key futura | PÚBLICO | frontend/config pública |
| VAPID private key futura | SECRET | backend/provider secret store |
| scheduler HMAC secret futuro | SECRET | backend y scheduler secret stores separados |
| `VITE_API_BASE_URL` | PÚBLICO | Cloudflare build environment; URL API sin credenciales |

La configuración Stage 2.8 implementa cookies, CSRF, Origin y CORS sin un secreto CSRF separado: el binding usa `SECRET_KEY` exclusivamente en backend. Turnstile, proveedor real de email, VAPID y scheduler permanecen pendientes y no deben recibir placeholders que aparenten ser secretos funcionales antes de su etapa.

La `SECRET_KEY` del `.env` local es deliberadamente de desarrollo y solo es aceptable en ese entorno. Producción debe usar una clave fuerte, única y exclusiva del backend mediante el secret store del proveedor. Este requisito operacional no reabre `SEC-SECRET-001`.

## 8. Frontend, build y DevTools

El único `VITE_*` consumido es `VITE_API_BASE_URL`. Es público por diseño. No se encontraron accesos frontend a nombres de secretos backend.

El build de producción completó sin proporcionar secretos. El scan de artefactos encontró cero URLs PostgreSQL, URLs con credenciales, claves privadas, nombres de secretos server-side o tokens Bearer literales. Las referencias a `Authorization` son código cliente público esperado. No se generaron archivos `.map`.

El bundle excede 500 kB minificado antes de gzip; es rendimiento, no hallazgo de secretos. La política recomendada es mantener source maps públicos desactivados o revisarlos antes de activarlos; si se suben a monitoreo, hacerlo de forma privada y sin variables sensibles.

### Checklist F12 para gates futuros

**Esperado/público:** bundle, manifest, assets, API base pública, site/VAPID public keys, responses que la cuenta está autorizada a ver y preferencias UI no sensibles.

**Prohibido:** hashes, digests, DB/signing/email/Turnstile/VAPID-private/scheduler secrets, account-action tokens crudos, datos de otros usuarios, detalles Calendar ocultos, internals de `GLOBAL_ADMIN`, ciphertext push o stack/SQL sensible.

Verificar Network, cookies, Local/Session Storage, IndexedDB, Cache Storage, service worker, React Query, source maps y errores. Logout/401 debe retirar sesión y cache de datos privados.

## 9. Storage del navegador tras Stage 2.8

Uso actual:

- La utilidad `authToken.ts` fue retirada del frontend activo.
- `api/client.ts` usa `credentials: include`, no adjunta Bearer y agrega el header CSRF solo en métodos unsafe.
- `AuthContext.tsx` mantiene identidad solo en memoria, restaura con `/api/v2/auth/me` y limpia TanStack Query en logout/401.
- `frontend/src/store/AuthContext.test.tsx` y `frontend/src/test/setup.ts`: verifican/limpian el storage de prueba.

No hay credencial de autenticación en `localStorage`, `sessionStorage` o IndexedDB. La cookie de sesión HttpOnly no es accesible a JavaScript; la cookie CSRF legible no contiene la credencial. TanStack Query permanece en memoria y no hay persister. No se encontraron logs del token.

La deuda `SEC-FE-001` queda cerrada para los paths activos V2. Solo un Workspace seleccionado u otra preferencia no sensible podrá persistirse si se aprueba. HttpOnly no elimina el riesgo XSS: un script activo aún puede originar requests, por lo que CSP y hardening continúan pendientes.

## 10. Service worker y cache

VitePWA usa `generateSW`, `navigateFallback` y `globPatterns` para JS, CSS, HTML y SVG. El build confirmó precache estático y ninguna ruta runtime de `/api`. Por tanto, respuestas autenticadas no se persisten actualmente en Cache Storage por configuración del proyecto.

V2 debe mantener las APIs privadas fuera de precache/runtime cache y probar que account, Calendar, notifications y Workspace data no sobreviven logout ni cambio de identidad.

## 11. Exposición por API y logs

`UserRead`/`UserProfileRead` actuales no exponen hashes. Los modelos físicos V2 sí contienen `hashed_password`, `global_role`, token digests y ciphertext push; no deben serializarse directamente. Cada DTO V2 requiere allowlist, `extra='forbid'`, campos actor/scope derivados y pruebas negativas exactas.

No se encontró logging explícito de passwords, Authorization, cookies, tokens o URLs de account actions. `SQL_ECHO` está desactivado por defecto, pero producción debe fijarlo en false. Varias rutas V1 convierten errores de dominio a texto; V2 debe centralizar códigos/mensajes seguros y jamás convertir excepciones DB/config arbitrarias en respuestas.

## 12. Tests y documentación

Los tests usan dominios/URLs locales o ficticios, emails de ejemplo y passwords/tokens de prueba. No se encontró material de proveedor o producción. La documentación actual no contiene credenciales reales; los ejemplos son placeholders. El valor histórico no se reproduce en ningún documento.

## 13. GitHub y supply chain

No existe `.github/`, workflows ni Dependabot configurado en el árbol. Debe verificarse manualmente en GitHub:

- secret scanning y push protection;
- visibilidad, forks y clones conocidos;
- branch protection y revisión requerida;
- permisos mínimos de Actions;
- deploy keys/tokens y environments;
- alertas Dependabot/dependency review.

En Stage 2.12 conviene evaluar gitleaks o detect-secrets en pre-commit/CI y TruffleHog para revisión histórica controlada. No se añadió dependencia ni workflow ahora.

## 14. Checklists de proveedores

### Cloudflare

- `VITE_API_BASE_URL`, dominios, site key Turnstile y VAPID public key son públicos.
- API token, Turnstile secret y scheduler HMAC permanecen en secrets del proveedor, nunca en Pages variables expuestas al bundle.
- Revisar preview deployments, build logs, headers CSP/referrer/frame y acceso de equipo.

### Render

- `DATABASE_URL`, `SECRET_KEY`, futuros secretos CSRF/email/VAPID/scheduler viven exclusivamente en environment secrets.
- Revisar que logs/build no impriman variables, `SQL_ECHO=false`, TLS, acceso de equipo y rotación.
- Los comandos de startup/migration no deben incluir valores inline.

### Neon

- Solo backend/migrator recibe credenciales; frontend y Cloudflare Pages nunca.
- `SEC-SECRET-001` está cerrado por rotación/revocación local; mantener separadas y rotadas las credenciales productivas.
- Revisar TLS, roles mínimos, separación runtime/migrator cuando se justifique, límites/conexiones y restore probado.
- Las guardas destructivas deben continuar rechazando hosts Neon/remotos.

## 15. Cierre de `SEC-SECRET-001`

El product owner no confirmó la no reutilización histórica y eligió la vía segura de remediación:

1. identificó la credencial como perteneciente al usuario PostgreSQL local `postgres`;
2. cambió/rotó la contraseña local;
3. actualizó la configuración local de LifeManager;
4. verificó la conexión sustituta mediante `SELECT 1`;
5. confirmó con ello la revocación de la credencial anterior.

No se imprimió, recuperó ni probó el valor antiguo o nuevo durante este cierre y no se contactó Neon/producción. La revisión histórica confirmó que el valor solo aparece en una ruta con host loopback y no en una URL PostgreSQL remota/Neon encontrada. `SEC-SECRET-001` queda **CERRADO por rotación/revocación**. La limpieza de historia, si se decide posteriormente, es hardening separado y no sustituye la revocación.

## 16. Cierre de Stage 2.2

Stage 2.2 queda **Completado técnicamente**: árbol, historia, Alembic/backend, entornos, bundle, source maps, storage, service worker, respuestas, logging, tests/docs y expectativas de proveedores fueron auditados; las brechas seguras del repositorio fueron mitigadas.

La acción manual `SEC-SECRET-001` fue cerrada por rotación/revocación y Stage 2.13 puede completarse. Este estado no afirma que GitHub, Cloudflare, Render o Neon hayan sido revisados desde sus consolas; esos controles y la `SECRET_KEY` productiva fuerte y única siguen siendo requisitos operacionales.
