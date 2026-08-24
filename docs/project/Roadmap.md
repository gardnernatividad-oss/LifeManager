# Roadmap de LifeManager V2.0.0

## Estado

El diseño funcional V2 está aprobado en `docs/requirements/Functional-V2.md` y ADR-007. El roadmap oficial V2 continúa después de cerrar esta línea base funcional. El detalle completo del baseline de ejecución todavía no está disponible dentro del repositorio, por lo que no se fabrican etapas adicionales.

Las etapas conocidas y aprobadas son:

## Estructura obligatoria

El roadmap conservará exactamente estas columnas:

| Fase | Etapa | Módulo | Estado |
|---|---|---|---|
| Phase 1 — V2 Preparation | Stage 1.1 | Technical audit of the current V1.0.0 baseline | Completado |
| Phase 1 — V2 Preparation | Stage 1.2 | Update and consolidate V2 functional documentation | Completado |
| Phase 1 — V2 Preparation | Stage 1.3 | Inventory of V1 components that are reusable, modifiable, or replaceable | Completado |
| Phase 1 — V2 Preparation | Stage 1.4 | Design of the V2 logical and physical data model | Completado |
| Phase 1 — V2 Preparation | Stage 1.5 | Constraints, relationships, indexes, data integrity and V1→V2 transition plan | Completado |
| Phase 1 — V2 Preparation | Stage 1.6 | Review and update architecture and technical decisions | Completado |
| Phase 1 — V2 Preparation | Stage 1.8 | Finalize target Architecture, Database and API documentation | Completado |
| Phase 1 — V2 Preparation | Stage 1.9 | Implement and validate the base V2 schema with Alembic | Completado |
| Phase 1 — V2 Preparation | Stage 1.10 | Create coherent V2 development data and fixtures | Completado |
| Phase 1 — V2 Preparation | Stage 1.11 | Technical gate for the V2 foundation before functional modules | Completado |
| Phase 2 — Security foundation and identity | Stage 2.1 | Initial V2 threat model and attack-surface inventory | Completado |
| Phase 2 — Security foundation and identity | Stage 2.2 | Secrets and configuration audit | Completado |
| Phase 2 — Security foundation and identity | Stage 2.3 | Global roles and account state | Completado |
| Phase 2 — Security foundation and identity | Stage 2.4 | Registration and approval | Completado |
| Phase 2 — Security foundation and identity | Stage 2.5 | Email verification | Completado |
| Phase 2 — Security foundation and identity | Stage 2.6 | Password recovery | Completado |
| Phase 2 — Security foundation and identity | Stage 2.7 | Password policy and hashing | Completado |
| Phase 2 — Security foundation and identity | Stage 2.8 | Session architecture | Completado |
| Phase 2 — Security foundation and identity | Stage 2.9 | Rate limiting and brute-force protection | Completado |
| Phase 2 — Security foundation and identity | Stage 2.10 | Turnstile integration | Completado |
| Phase 2 — Security foundation and identity | Stage 2.11 | Server validation and error handling | Pendiente |
| Phase 2 — Security foundation and identity | Stage 2.12 | Security tests | Pendiente |
| Phase 2 — Security foundation and identity | Stage 2.13 | Identity and security gate | Pendiente |

`Estado` solo puede contener:

- Completado
- Pendiente

Los stages documentales conocidos hasta 1.8 quedan cerrados por el modelo, plan de transición, `V2-Architecture-Baseline.md`, contrato API y ADR-008–012. Stage 1.9 implementó la base física V2, Stage 1.10 añadió fixtures y Stage 1.11 cerró el gate técnico. Stage 2.1 estableció el threat model. Stage 2.2 auditó exposición y mantiene una acción manual antes de 2.13. Stages 2.3–2.7 establecieron identidad, recovery y política Argon2id. Stage 2.8 estableció sesión cookie/CSRF, Stage 2.9 rate limiting PostgreSQL y Stage 2.10 Turnstile server-side en las tres rutas públicas seleccionadas.

## Referencia histórica

El roadmap utilizado para V1 se conserva en `docs/project/V1-Roadmap-Historical.md` y no orienta la secuencia V2.
