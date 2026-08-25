# Contexto de LifeManager

## Estado del producto

LifeManager V1.0.0 es la implementación publicada y la línea base técnica. El tag anotado `v1.0.0` resuelve al commit `fafa8844f83763c837aa423d0773cd6d5782752c`.

LifeManager V2.0.0 está en preparación. Su comportamiento aprobado está documentado en `docs/requirements/Functional-V2.md` y ADR-007. La base física, recurrencia, fixtures y gate técnico de Phase 1 están implementados; las APIs y pantallas funcionales V2 todavía no lo están.

## Fuentes de autoridad

| Alcance | Fuente |
|---|---|
| Runtime y comportamiento V1 actual | Código en el tag `v1.0.0`, `docs/requirements/Functional.md`, ADR-005 y ADR-006 |
| Modelo físico V1 actual | `docs/database/V1-Target-Data-Model.md` y `docs/database/ERD.md` |
| Objetivo funcional V2 aprobado | `docs/requirements/Functional-V2.md` y ADR-007 |
| Arquitectura técnica V2 aprobada; foundation parcialmente implementada | `docs/architecture/V2-Architecture-Baseline.md` y ADR-009–012 |
| Permisos y autorización V2 | `docs/architecture/Permissions.md` y ADR-011 |
| Modelo lógico/físico V2 aprobado e implementado | `docs/database/V2-Target-Data-Model.md`, `docs/database/V2-ERD.md`, `docs/database/V2-Data-Model-Status.md` y ADR-008 |
| Transición física V2 implementada y validada solo en DB local/test desechable | `docs/database/V2-Transition-Implementation-Plan.md` |
| Contrato API transversal V2, no implementado | `docs/api/V2-Contract-Status.md`, ADR-010 y ADR-011 |
| Seguridad y requisitos no funcionales V2 | `docs/requirements/NonFunctional.md` |
| Threat model y backlog de seguridad V2 | `docs/security/V2-Threat-Model.md` |
| Auditoría de secretos, bundle, storage y configuración cloud V2 | `docs/security/V2-Secrets-and-Exposure-Audit.md` |
| Roadmap V2 | `docs/project/Roadmap.md` |
| Referencia histórica V1 | tag `v1.0.0`, `docs/requirements/Functional.md`, `docs/database/V1-Target-Data-Model.md`, `docs/database/ERD.md`, ADR-005 y ADR-006 |
| Futuro no aprobado | `docs/requirements/FutureIdeas.md`, cuando se documente expresamente como idea |

En caso de contradicción funcional prevalecen `Functional-V2.md` y ADR-007. En cada asunto técnico prevalece la fuente especializada indicada en la tabla y su ADR correspondiente. Ningún documento V2 implica que el runtime actual ya tenga esa capacidad.

## V1 actual

- PWA personal en español con autenticación Bearer JWT.
- Un Personal Workspace creado automáticamente por usuario.
- Categorías y catálogo de Tareas.
- Planificación, Revisión, Seguimiento y Reportes para Tareas, Pendientes y Proyectos con componentes internos `ProjectStep` (Etapas en la terminología V2).
- Inicio operativo y Configuración de perfil/zona horaria.
- Backend FastAPI, SQLAlchemy 2.x, Alembic y PostgreSQL.
- Frontend React, TypeScript, Vite y TanStack Query.

V1 no expone colaboración, responsables, Calendario/Actividades, notificaciones, historia cronológica de Pendientes/Etapas ni administración global.

## V2 aprobado

- Personal Workspace y Workspaces compartidos.
- Roles globales separados de roles de Workspace.
- Responsables para Tareas, Pendientes y Etapas.
- Vistas globales Inicio, Revisión y Mi calendario.
- Actividades, Calendario consolidado y privacidad para comparación.
- Historia cronológica de Pendientes y Etapas.
- Centro de notificaciones como overlay para eventos relevantes de membresía, asignación, Actividades y recordatorios; sin avisos por comentarios.
- Registro restringido con anti-bot, verificación de correo, aprobación global y requisitos de seguridad reforzados.
- UX mobile-first con páginas internas de detalle.

## Transición

Los datos V1 existentes son de prueba/no esenciales. El reset controlado V1→V2 fue implementado y validado exclusivamente sobre bases locales/test desechables; no se ejecutó contra producción ni una base compartida. Las migraciones históricas y el historial Git no se editan. Tras publicar V2 y comenzar uso real, los resets destructivos dejan de ser aceptables y toda evolución deberá preservar datos de producción.

Phase 1 cerró el baseline documental, los 25 modelos V2, la revisión `e4f5a6b7c8d9`, constraints PostgreSQL, recurrencia, fixtures y el gate técnico. Phase 2 completó threat model y auditoría de exposición. Stages 2.4–2.7 implementaron el lifecycle de identidad, recovery y política Argon2id. Stage 2.8 implementó sesión cookie HttpOnly/CSRF y Stage 2.9 rate limiting PostgreSQL distribuido. Stage 2.10 añadió Turnstile server-side a registro, recovery y reenvío con integración mínima en el registro frontend. Stage 2.11 cerró validación/input/output y Stage 2.12 la regresión ofensiva. Stage 2.13 queda Completado: aprobó el gate técnico local, incluidos 47 tests PostgreSQL sobre una base desechable, y cerró `SEC-SECRET-001` mediante rotación/revocación de la credencial PostgreSQL local histórica. El Personal Workspace nace únicamente tras aprobación global. Siguen pendientes como requisitos operacionales las credenciales Cloudflare productivas, una `SECRET_KEY` productiva fuerte, única y backend-only, el proveedor real de email, CSP/security headers y hardening operacional.

Stage 3.1 estableció la foundation Workspace definitiva sin cambiar el esquema ni publicar rutas nuevas. La autorización privada se deriva de cuenta `ACTIVE` y membresía `ACTIVE`, nunca de `GLOBAL_ADMIN`; el rol Propietario se deriva de `owner_user_id`. Personal mantiene un único owner, no admite miembros adicionales y no puede eliminarse, transferirse ni convertirse mediante operaciones ordinarias. La colaboración Shared, sus invitaciones, membresías y transferencia se implementarán en etapas posteriores sobre esta frontera.

Stage 3.2 añadió la creación autenticada de Workspace Compartido. El cliente aporta únicamente el nombre; el backend fija `SHARED`, deriva al owner de la sesión, crea su membresía `ACTIVE` en la misma transacción y devuelve una proyección mínima. Personal continúa siendo system-only durante aprobación. Listado/selector, invitaciones, administración de miembros, transferencia y eliminación Shared siguen diferidos.

## Principios

- Distinguir implementación actual de objetivo futuro.
- Autorizar siempre en servidor y aislar por Workspace.
- Mantener historia operativa salvo excepciones explícitas.
- Usar terminología española aprobada en la interfaz.
- Diseñar primero para móvil vertical sin degradar desktop.
- Tratar seguridad como requisito transversal, no como etapa opcional final.
