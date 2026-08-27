# Roadmap de LifeManager V2.0.0

> **Actualización Stage 3.6:** Completado. Se implementaron listado, selector,
> permisos derivados, reactivación e integración colaborativa. La fila histórica
> de la tabla que aún indique `Pendiente` para 3.6 queda sustituida por esta
> actualización hasta la siguiente consolidación editorial.

## Estado

El diseño funcional V2 está aprobado en `docs/requirements/Functional-V2.md` y ADR-007. El roadmap oficial V2 continúa después de cerrar esta línea base funcional. El detalle completo del baseline de ejecución todavía no está disponible dentro del repositorio, por lo que no se fabrican etapas adicionales.

Las etapas conocidas y aprobadas son:

## Estructura obligatoria

El roadmap conservará exactamente estas columnas:

| Fase | Etapa | Módulo | Estado |
|---|---|---|---|
| Phase 0 — Diseño funcional | Stage 0.1 | Definición del alcance funcional de LifeManager V2.0.0 | Completado |
| Phase 0 — Diseño funcional | Stage 0.2 | Navegación, terminología y arquitectura de información V2 | Completado |
| Phase 0 — Diseño funcional | Stage 0.3 | Inventario de pantallas y flujos funcionales V2 | Completado |
| Phase 0 — Diseño funcional | Stage 0.4 | Sistema de diseño, componentes y criterios responsive | Completado |
| Phase 0 — Diseño funcional | Stage 0.5 | Consolidación y aprobación de la línea base funcional V2 | Completado |
| Phase 1 — V2 Preparation | Stage 1.1 | Technical audit of the current V1.0.0 baseline | Completado |
| Phase 1 — V2 Preparation | Stage 1.2 | Update and consolidate V2 functional documentation | Completado |
| Phase 1 — V2 Preparation | Stage 1.3 | Inventory of V1 components that are reusable, modifiable, or replaceable | Completado |
| Phase 1 — V2 Preparation | Stage 1.4 | Design of the V2 logical and physical data model | Completado |
| Phase 1 — V2 Preparation | Stage 1.5 | Constraints, relationships, indexes, data integrity and V1→V2 transition plan | Completado |
| Phase 1 — V2 Preparation | Stage 1.6 | Review and update architecture and technical decisions | Completado |
| Phase 1 — V2 Preparation | Stage 1.7 | Estrategia de reset de datos V1 y transición del esquema a V2 | Completado |
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
| Phase 2 — Security foundation and identity | Stage 2.11 | Server validation and error handling | Completado |
| Phase 2 — Security foundation and identity | Stage 2.12 | Security tests | Completado |
| Phase 2 — Security foundation and identity | Stage 2.13 | Identity and security gate | Completado |
| Phase 3 — Workspaces y colaboración base | Stage 3.1 | Adaptación del modelo Personal y Compartido de Workspace | Completado |
| Phase 3 — Workspaces y colaboración base | Stage 3.2 | Creación de Workspace Compartido | Completado |
| Phase 3 — Workspaces y colaboración base | Stage 3.3 | Invitaciones a Workspace Compartido | Completado |
| 3. Workspaces y colaboración base | 3.4 | Administración, salida y ciclo de membresías de Workspaces compartidos | Completado |
| 3. Workspaces y colaboración base | 3.5 | Gestión avanzada de Workspace: propiedad, desactivación, eliminación y responsabilidades futuras | Completado |
| 3. Workspaces y colaboración base | 3.6 | Listado, selector, permisos e integración colaborativa de Workspaces | Completado |
| 3. Workspaces y colaboración base | 3.7 | Gate funcional, autorización e aislamiento de Workspaces | Completado |
| 4. Tablas maestras | 4.1 | Categorías y catálogos maestros de Tareas y Actividades | Completado |
| 4. Tablas maestras | 4.2 | Reclasificación histórica, ciclo de maestros y selectores reutilizables | Completado |
| 4. Tablas maestras | 4.3 | UX, autorización y gate de Tablas maestras | Completado |
| 5. Tareas | 5.1 | Planificación, asignación y ciclo de vida de Tareas | Completado |
| 5. Tareas | 5.2 | Recurrencia finita y generación de ocurrencias de Tareas | Completado |
| 5. Tareas | 5.3 | Gestión de ocurrencias/series, listado y experiencia responsive | Completado |
| 5. Tareas | 5.4 | Autorización, pruebas y gate de Tareas | Completado |
| 6. Pendientes | 6.1 | Planificación, ciclo, avance y cumplimiento de Pendientes | Completado |
| 6. Pendientes | 6.2 | Historial, comentarios y detalle de Pendientes | Completado |
| 6. Pendientes | 6.3 | Listado, filtros y UX mobile-first de Pendientes | Pendiente |
| 6. Pendientes | 6.4 | Autorización, pruebas y gate de Pendientes | Pendiente |
| 7. Proyectos y Etapas | 7.1 | Gestión de Proyectos, liderazgo y ciclo general | Pendiente |
| 7. Proyectos y Etapas | 7.2 | Etapas, responsables, pesos, avance y cumplimiento | Pendiente |
| 7. Proyectos y Etapas | 7.3 | Historial, comentarios y navegación jerárquica Proyecto → Etapa | Pendiente |
| 7. Proyectos y Etapas | 7.4 | UX mobile-first, autorización, pruebas y gate | Pendiente |
| 8. Calendario y Actividades | 8.1 | Gestión de Actividades, organizador, participantes y Workspace | Pendiente |
| 8. Calendario y Actividades | 8.2 | Recurrencia, recordatorios y modificaciones de series de Actividades | Pendiente |
| 8. Calendario y Actividades | 8.3 | Mi calendario consolidado y experiencia desktop/móvil | Pendiente |
| 8. Calendario y Actividades | 8.4 | Privacidad de Calendario y comparación de disponibilidad | Pendiente |
| 8. Calendario y Actividades | 8.5 | Autorización, privacidad, pruebas y gate de Calendario | Pendiente |
| 9. Revisión | 9.1 | Motor global y reglas de selección de Revisión | Pendiente |
| 9. Revisión | 9.2 | Flujo de revisión por bloques y experiencia mobile-first | Pendiente |
| 9. Revisión | 9.3 | Autorización, pruebas y gate de Revisión | Pendiente |
| 10. Inicio | 10.1 | Inicio global, resumen diario y accesos rápidos | Pendiente |
| 10. Inicio | 10.2 | Responsive, pruebas y gate de Inicio | Pendiente |
| 11. Notificaciones y recordatorios | 11.1 | Infraestructura de eventos, campana, push y scheduler | Pendiente |
| 11. Notificaciones y recordatorios | 11.2 | Recordatorios diarios, Revisión y seguimientos configurables | Pendiente |
| 11. Notificaciones y recordatorios | 11.3 | Recordatorios de Actividades, agrupación y deep links | Pendiente |
| 11. Notificaciones y recordatorios | 11.4 | Seguridad, pruebas y gate de notificaciones | Pendiente |
| 12. Reportes | 12.1 | Infraestructura, filtros y agregaciones de Reportes | Pendiente |
| 12. Reportes | 12.2 | Reportes de Tareas, Pendientes y Proyectos/Etapas | Pendiente |
| 12. Reportes | 12.3 | Reportes de Actividades y reclasificación histórica | Pendiente |
| 12. Reportes | 12.4 | Visualización, responsive, autorización y gate de Reportes | Pendiente |
| 13. Configuración | 13.1 | Perfil, estructura y configuración general | Pendiente |
| 13. Configuración | 13.2 | Recordatorios, seguimientos y privacidad de Calendario | Pendiente |
| 13. Configuración | 13.3 | Gestión de Workspaces, seguridad visible y Acerca de | Pendiente |
| 13. Configuración | 13.4 | Responsive, permisos, pruebas y gate de Configuración | Pendiente |
| 14. Administración global | 14.1 | Consola privada de administración global y usuarios | Pendiente |
| 14. Administración global | 14.2 | Seguridad, auditoría, pruebas y gate administrativo | Pendiente |
| 15. Integración UX y PWA | 15.1 | Integración visual, navegación y patrones comunes de UX | Pendiente |
| 15. Integración UX y PWA | 15.2 | Auditoría responsive, mobile-first y accesibilidad | Pendiente |
| 15. Integración UX y PWA | 15.3 | PWA, caché, actualización segura y gate UX/PWA | Pendiente |
| 16. Hardening de seguridad | 16.1 | Threat model final, secretos y superficie frontend | Pendiente |
| 16. Hardening de seguridad | 16.2 | Autenticación, autorización, aislamiento y privacidad final | Pendiente |
| 16. Hardening de seguridad | 16.3 | Injection, XSS, API, CORS, CSP, headers y navegador | Pendiente |
| 16. Hardening de seguridad | 16.4 | Dependencias, supply chain, infraestructura, correo y push | Pendiente |
| 16. Hardening de seguridad | 16.5 | Pruebas ofensivas, remediación y gate formal de seguridad | Pendiente |
| 17. QA integral V2 | 17.1 | Gate técnico integral backend/frontend/Alembic | Pendiente |
| 17. QA integral V2 | 17.2 | QA E2E Personal, colaborativo y casos límite | Pendiente |
| 17. QA integral V2 | 17.3 | QA desktop, móvil, PWA y navegadores objetivo | Pendiente |
| 17. QA integral V2 | 17.4 | Corrección de defectos, regresión y gate funcional V2.0.0 | Pendiente |
| 18. Publicación V2.0.0 | 18.1 | Release candidate, documentación y preparación de datos | Pendiente |
| 18. Publicación V2.0.0 | 18.2 | Despliegue de infraestructura, backend, esquema y frontend/PWA | Pendiente |
| 18. Publicación V2.0.0 | 18.3 | Configuración productiva de secretos, dominios, HTTPS y servicios | Pendiente |
| 18. Publicación V2.0.0 | 18.4 | Smoke test, seguridad y QA final en producción | Pendiente |
| 18. Publicación V2.0.0 | 18.5 | Release oficial LifeManager v2.0.0 e inicio de datos reales | Pendiente |

`Estado` solo puede contener:

- Completado
- Pendiente

Phase 0 preserva los cinco bloques de diseño funcional acreditados por Functional‑V2, ADR‑007 y la documentación UI. Los stages documentales 1.1–1.8 quedan cerrados por la auditoría, el modelo, la estrategia de reset/transición, `V2-Architecture-Baseline.md`, el contrato API y ADR-008–012. Stage 1.9 implementó la base física V2, Stage 1.10 añadió fixtures y Stage 1.11 cerró el gate técnico. Stage 2.1 estableció el threat model. Stage 2.2 auditó exposición. Stages 2.3–2.7 establecieron identidad, recovery y política Argon2id. Stage 2.8 estableció sesión cookie/CSRF, Stage 2.9 rate limiting PostgreSQL y Stage 2.10 Turnstile server-side en las tres rutas públicas seleccionadas. Stage 2.11 cerró validación autoritativa y Stage 2.12 la regresión ofensiva. Stage 2.13 queda `Completado`: superó sus controles técnicos y PostgreSQL locales y cerró `SEC-SECRET-001` mediante rotación/revocación; ver `docs/security/V2-Identity-Security-Gate.md`. La configuración de una `SECRET_KEY` productiva fuerte, única y backend-only permanece como requisito operacional de despliegue, no como hallazgo abierto de Phase 2.

Stage 3.1 consolidó la frontera reutilizable de autorización Workspace, explicitó las invariantes Personal/Shared y protegió centralmente las mutaciones que Personal prohíbe. No añadió rutas ni cambió el esquema: creación Shared, invitaciones, administración de miembros y transferencia Shared pertenecen a etapas posteriores.

Stage 3.2 implementó `POST /api/v2/workspaces` para que una cuenta ACTIVE cree un Workspace `SHARED`. Owner, kind y membresía ACTIVE se derivan en servidor y se persisten atómicamente. Invitaciones, administración de miembros, selector/listado y transferencia continúan pendientes.

Stage 3.3 implementó invitaciones exclusivamente a cuentas LifeManager `ACTIVE` existentes. Solo el propietario de un Workspace `SHARED` puede crear o cancelar; el destinatario autenticado puede listar, aceptar o rechazar. La aceptación crea o reactiva atómicamente la misma membresía, restablece privacidad `HIDE` y nunca transfiere propiedad ni rol global. Las invitaciones vencen a los 14 días y se excluyen de listados accionables sin scheduler. Email, centro de notificaciones y administración general de miembros continúan diferidos.

Stage 3.4 implementó el listado seguro de membresías Shared, salida voluntaria y retiro de Miembros ordinarios por el Propietario. Las transiciones preservan una única fila histórica (`ACTIVE → LEFT/REMOVED`), fijan `ended_at`, incrementan `lock_version` y revocan acceso inmediatamente. Propietario, Personal y `GLOBAL_ADMIN` no obtienen atajos; una invitación nueva puede reactivar la misma fila y restablece privacidad `HIDE`. El gate operacional corrigió el aislamiento Alembic/test mediante target explícito y allowlist fail-closed que excluye la base compartida `lifemanager`. Transferencia, eliminación Shared y tratamiento de responsabilidades futuras pertenecen a Stage 3.5; selector e interfaz de gestión pertenecen a 3.6/13.3.

Stage 3.5 añadió lifecycle Workspace `ACTIVE/INACTIVE`, transferencia Shared,
desactivación conservadora, hard delete exclusivamente vacío y resolución
atómica de responsabilidades futuras al salir o retirar miembros. Personal y
`GLOBAL_ADMIN` no obtienen atajos. `can_delete` se deriva en backend; la gestión
visual y reactivación permanecen en Stage 3.6.

Stage 3.6 completó listado operacional y de gestión, selector/contexto y la
administración colaborativa frontend. Stage 3.7 cerró el gate integral de
Personal/Shared, ownership, invitaciones, membresías, lifecycle, IDOR,
mass assignment, cache y PostgreSQL. El gate corrigió el orden de locks de
invitaciones a `Workspace → WorkspaceInvitation`; la matriz y evidencia quedan
en `docs/security/V2-Workspace-Gate.md`. Las autorizaciones particulares de
cada dominio continúan en sus stages respectivos.

Después de Stage 3.3, el alcance futuro se reagrupará en bloques de implementación coherentes sin reducir funcionalidad. La correspondencia completa entre historia, requisitos autoritativos y los 60 stages pendientes está en [`V2-Roadmap-Regrouping-Traceability.md`](V2-Roadmap-Regrouping-Traceability.md).

## Referencia histórica

El roadmap utilizado para V1 se conserva en `docs/project/V1-Roadmap-Historical.md` y no orienta la secuencia V2.
