# Requisitos no funcionales de LifeManager V2.0.0

## Autoridad

Este documento complementa `Functional-V2.md`; si existe contradicción, prevalecen esa especificación y ADR-007.

## Seguridad

- El threat model vigente y su matriz de riesgos se mantienen en `docs/security/V2-Threat-Model.md`; cada control debe enlazar una prueba antes de cerrar su gate.
- Seguridad transversal durante todas las etapas y gate explícito antes de producción.
- Registro restringido con Turnstile, creación del estado de cuenta requerido, verificación de correo, espera de aprobación global y activación solo después de aprobación por `GLOBAL_ADMIN`.
- Contraseñas de al menos ocho caracteres con mayúscula, minúscula y símbolo.
- Rate limiting, protección contra fuerza bruta y anti-bot/Cloudflare Turnstile.
- Recuperación de contraseña con respuestas neutrales que no revelan la existencia de cuentas.
- Sesión V2 mediante JWT corto en cookie HttpOnly/Secure, restaurada por `/me`, sin secretos en localStorage; CSRF double-submit para métodos unsafe.
- Autorización server-side con aislamiento de usuario y Workspace.
- Validación server-side, protección de mass assignment y consultas parametrizadas.
- Prevención de XSS e inyección de contenido; respuestas API mínimas.
- Secretos ausentes de bundles, source, logs y respuestas.
- CORS, CSP, security headers y HTTPS/TLS revisados para producción.
- Origins CORS exactos con credentials; GLOBAL_ADMIN no bypassa contenido privado de Workspaces.
- SAST, SCA, dependencias y cadena de suministro auditados.
- Seguridad de Neon, Render, Cloudflare y GitHub incluida en el gate.
- RLS evaluado como defensa adicional, no asumido como obligatorio sin análisis.
- Ningún secreto ni token de sesión se almacena en variables `VITE_*`, bundles, service-worker caches o Web Storage en V2.
- Jobs internos exigen autenticación independiente con firma, freshness y protección de replay; no reutilizan cookies de usuario.
- Logs y errores redactan credenciales, cookies, tokens, recovery links, firmas, endpoints push, SQL sensible y cuerpos de autenticación.

## Privacidad e integridad

- Disponibilidad de Calendario respeta Mostrar detalles, Solo disponibilidad u Ocultar.
- Las políticas colaborativas se aplican al calendario consolidado según autorización.
- El pasado no se reescribe por operaciones sobre series o membresías salvo excepciones funcionales explícitas.
- Los historiales de Pendientes y Etapas preservan orden, autoría y contenido necesario.

## Experiencia y accesibilidad

- UX mobile-first y uso vertical prioritario.
- Navegación y formularios accesibles por teclado.
- Estados no comunicados exclusivamente mediante color.
- Carga, error, vacío, conflicto y reintento tratados explícitamente.
- Fechas visibles `dd/mm/yyyy`; semana desde lunes; interfaz Spanish-first.

## Calidad y operación

- Pruebas unitarias, de integración, autorización, aislamiento, concurrencia y seguridad.
- Migraciones verificadas en entornos no productivos antes de despliegue.
- Observabilidad sin exponer secretos ni datos sensibles.
- Dependencias e infraestructura actualizadas mediante cambios revisados y reproducibles.
- PostgreSQL real obligatorio para constraints, locks, triggers, concurrencia y migraciones; mocks no sustituyen integración crítica.
- HTTP real obligatorio para cookie/CSRF/CORS, IDOR, privacidad y journeys multiusuario críticos.
- `/health` comprueba liveness sin DB y `/ready` comprueba PostgreSQL con timeout sin revelar configuración.
- Frontend valida TypeScript, ESLint, tests y build; backend valida suite, compilación, migraciones e integración antes de deploy.
