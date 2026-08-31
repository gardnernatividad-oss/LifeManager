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
| Fase 0 | 0.1 | Cierre integral del alcance funcional de LifeManager V2.0.0 | Completado |
| Fase 0 | 0.2 | Terminología, navegación, Workspaces y comportamiento general de la interfaz | Completado |
| Fase 0 | 0.3 | Reglas funcionales de Tareas, Pendientes, Proyectos y Etapas | Completado |
| Fase 0 | 0.4 | Reglas funcionales de Calendario, Actividades, participantes y privacidad | Completado |
| Fase 0 | 0.5 | Revisión, Inicio, recordatorios, notificaciones, Reportes y Configuración | Completado |
| Fase 1 | 1.1 | Auditoría técnica del estado de LifeManager V1.0.0 como base de V2 | Completado |
| Fase 1 | 1.2 | Actualización y consolidación de documentación funcional V2 | Completado |
| Fase 1 | 1.3 | Inventario de componentes reutilizables, modificables y reemplazables de V1 | Completado |
| Fase 1 | 1.4 | Diseño lógico y físico del modelo de datos V2 | Completado |
| Fase 1 | 1.5 | Constraints, relaciones, índices e integridad de datos del modelo V2 | Completado |
| Fase 1 | 1.6 | Revisión de arquitectura, capas, servicios y decisiones técnicas V2 | Completado |
| Fase 1 | 1.7 | Estrategia de reset de datos V1 y transición controlada del esquema a V2 | Completado |
| Fase 1 | 1.8 | Documentación objetivo de arquitectura, base de datos y API V2 | Completado |
| Fase 1 | 1.9 | Implementación y validación del esquema base V2 mediante Alembic | Completado |
| Fase 1 | 1.10 | Datos de prueba y fixtures canónicos coherentes para desarrollo V2 | Completado |
| Fase 1 | 1.11 | Gate técnico integral de la base V2 antes de módulos funcionales | Completado |
| Fase 2 | 2.1 | Threat model inicial V2 e inventario de superficies de ataque | Completado |
| Fase 2 | 2.2 | Auditoría inicial de secretos, `.env`, Git, frontend bundle y configuración cloud | Completado |
| Fase 2 | 2.3 | Modelo de roles globales y separación estricta de roles de Workspace | Completado |
| Fase 2 | 2.4 | Registro mediante solicitud y aprobación del administrador global | Completado |
| Fase 2 | 2.5 | Verificación segura de correo electrónico | Completado |
| Fase 2 | 2.6 | Recuperación y restablecimiento seguro de contraseña | Completado |
| Fase 2 | 2.7 | Política de contraseñas, hashing y protección de credenciales | Completado |
| Fase 2 | 2.8 | Arquitectura definitiva de sesiones, cookies/JWT, expiración y logout | Completado |
| Fase 2 | 2.9 | Rate limiting de autenticación, brute force y protección contra enumeración | Completado |
| Fase 2 | 2.10 | Cloudflare Turnstile y protección anti-bot en flujos públicos | Completado |
| Fase 2 | 2.11 | Validación server-side y manejo seguro de errores de autenticación | Completado |
| Fase 2 | 2.12 | Tests de autenticación, registro, recuperación, roles y escenarios de abuso | Completado |
| Fase 2 | 2.13 | Gate de seguridad de identidad y autenticación sobre PostgreSQL | Completado |
| Fase 3 | 3.1 | Modelo funcional y técnico de Workspaces Personal y Compartido | Completado |
| Fase 3 | 3.2 | Creación automática y protección del Workspace Personal | Completado |
| Fase 3 | 3.3 | Propietario, Miembro, membresías y reglas colaborativas fundamentales | Completado |
| Fase 3 | 3.4 | Administración, salida, retiro, reingreso y ciclo de membresías Shared | Completado |
| Fase 3 | 3.5 | Transferencia de propiedad, desactivación/eliminación y resolución de responsabilidades futuras | Completado |
| Fase 3 | 3.6 | Listados, selector contextual, permisos e integración frontend de Workspaces | Completado |
| Fase 3 | 3.7 | Gate funcional, autorización, IDOR y aislamiento entre Workspaces | Completado |
| Fase 4 | 4.1 | Categorías y catálogos maestros Workspace-scoped de Tareas y Actividades | Completado |
| Fase 4 | 4.2 | Reclasificación histórica dinámica, ciclo de maestros y selectores reutilizables | Completado |
| Fase 4 | 4.3 | UX, autorización, integridad y gate de Tablas maestras | Completado |
| Fase 5 | 5.1 | Planificación, asignación, estados y ciclo de vida de Tareas | Completado |
| Fase 5 | 5.2 | Recurrencia finita diaria/semanal/mensual y generación atómica de ocurrencias | Completado |
| Fase 5 | 5.3 | Gestión de ocurrencias y series, listado, filtros y experiencia responsive | Completado |
| Fase 5 | 5.4 | Autorización, concurrencia, PostgreSQL, regresión y gate de Tareas | Completado |
| Fase 6 | 6.1 | Planificación, vigencia, responsable, avance, finalización y cumplimiento de Pendientes | Completado |
| Fase 6 | 6.2 | Historial, comentarios, correcciones y detalle de Pendientes | Completado |
| Fase 6 | 6.3 | Listado, filtros, paginación y experiencia mobile-first de Pendientes | Completado |
| Fase 6 | 6.4 | Autorización, concurrencia, PostgreSQL, regresión y gate de Pendientes | Completado |
| Fase 7 | 7.1 | Gestión de Proyectos, Categoría, liderazgo, vigencia y ciclo general | Completado |
| Fase 7 | 7.2 | Etapas, responsables, orden, pesos, avance, finalización y cumplimiento | Completado |
| Fase 7 | 7.3 | Historial, comentarios y navegación jerárquica Proyecto → Etapas → Etapa | Completado |
| Fase 7 | 7.4 | UX mobile-first, autorización, concurrencia, PostgreSQL y gate de Proyectos/Etapas | Completado |
| Fase 8 | 8.1 | Planificación de Actividades, Workspace, organizador y participantes | Completado |
| Fase 8 | 8.2 | Recurrencia finita, identidad, zonas horarias y generación atómica de Actividades | Completado |
| Fase 8 | 8.3 | Mi calendario global consolidado y experiencia Día/Semana desktop-móvil | Completado |
| Fase 8 | 8.4 | Privacidad y comparación diaria de calendarios entre miembros Shared | Completado |
| Fase 8 | 8.5 | Gestión de ocurrencias/series, cancelación, salida de participantes, autorización y gate | Completado |
| 9. Corrección de paridad funcional | 9.1 | Auditoría integral de Fases 3–8 contra el diseño funcional final y detección de desviaciones | Completado |
| 9. Corrección de paridad funcional | 9.2 | Corrección de Tareas y Tablas: resultados corregibles, Otra tarea/Otra actividad y clasificación/reportabilidad | Pendiente |
| 9. Corrección de paridad funcional | 9.3 | Corrección de Proyectos/Etapas: orden visual, pesos 100.00%, precisión, vigencia y corrección de finalizados | Completado |
| 9. Corrección de paridad funcional | 9.4 | Corrección de Calendario: vistas Día/Semana/Mes, resúmenes diarios, vistas Workspace y comparación colaborativa | Completado |
| 9. Corrección de paridad funcional | 9.5 | Regresión integral, autorización, PostgreSQL, responsive y gate de paridad funcional de Fases 3–8 | Completado |
| 10. Revisión | 10.1 | Motor global y reglas de selección de Tareas, Pendientes y Etapas para Revisión | Completado |
| 10. Revisión | 10.2 | Revisión por bloques plegables, guardado independiente y correcciones de Tareas/Pendientes/Etapas | Completado |
| 10. Revisión | 10.3 | UX mobile-first, autorización, atomicidad por bloque, PostgreSQL y gate de Revisión | Completado |
| 11. Inicio | 11.1 | Inicio global: resumen inmediato de Hoy, accesos a Tareas/Pendientes/Etapas/Actividades y atención diaria | Completado |
| 11. Inicio | 11.2 | Próximas Actividades/días, navegación, responsive, consultas eficientes y gate de Inicio | Completado |
| 12. Notificaciones y recordatorios | 12.1 | Infraestructura de eventos, centro de notificaciones, push, scheduler y preferencias técnicas | Completado |
| 12. Notificaciones y recordatorios | 12.2 | Recordatorio diario, Revisión diaria y seguimientos configurables de Pendientes/Proyectos | Completado |
| 12. Notificaciones y recordatorios | 12.3 | Recordatorios semanales de Pendientes y Proyectos | Completado |
| 12. Notificaciones y recordatorios | 12.4 | Recordatorios de Actividades y gate integral de Notificaciones | Completado |
| 12. Notificaciones y recordatorios | 12.5 | Reconciliación frontend V2 y gate de integración | Completado |
| 13. Reportes | 13.1 | Motor global de Reportes, alcance Workspace, periodos, filtros y agregaciones reutilizables | Completado |
| 13. Reportes | 13.2 | Reportes de Tareas, Pendientes y Proyectos/Etapas: cumplimiento, avance, categorías y evolución | Pendiente |
| 13. Reportes | 13.3 | Reportes de Actividades, Otras actividades/tareas y reclasificación histórica dinámica por maestros | Pendiente |
| 13. Reportes | 13.4 | Tablas históricas, gráficos, filtros, responsive, exportabilidad prevista, autorización y gate de Reportes | Pendiente |
| 14. Configuración | 14.1 | Perfil de usuario, cuenta, idioma, zona horaria y estructura general de Configuración | Pendiente |
| 14. Configuración | 14.2 | Configuración de Recordatorio diario, Revisión diaria, seguimientos y privacidad de Calendario | Pendiente |
| 14. Configuración | 14.3 | Gestión de Workspaces, membresías/propiedad, seguridad visible de cuenta y Acerca de | Pendiente |
| 14. Configuración | 14.4 | Responsive, permisos, validaciones, PostgreSQL y gate de Configuración | Pendiente |
| 15. Administración global | 15.1 | Consola privada GLOBAL_ADMIN: solicitudes de registro, usuarios, estados y operaciones administrativas | Pendiente |
| 15. Administración global | 15.2 | Aislamiento del administrador global, auditoría, seguridad, pruebas y gate administrativo | Pendiente |
| 16. Integración UX y PWA | 16.1 | Integración visual completa, navegación global/contextual y patrones comunes de interacción | Pendiente |
| 16. Integración UX y PWA | 16.2 | Auditoría desktop/mobile-first, tablas, formularios, estados visuales y accesibilidad | Pendiente |
| 16. Integración UX y PWA | 16.3 | PWA, instalación, service worker, caché, actualización segura y gate UX/PWA | Pendiente |
| 17. Hardening de seguridad | 17.1 | Threat model final, secretos, Git/cloud, bundles y superficie expuesta al navegador | Pendiente |
| 17. Hardening de seguridad | 17.2 | Autenticación, sesiones, autorización, IDOR, aislamiento Workspace/usuario y privacidad final | Pendiente |
| 17. Hardening de seguridad | 17.3 | Injection, XSS, mass assignment, API mínima, CORS, CSP, headers y almacenamiento del navegador | Pendiente |
| 17. Hardening de seguridad | 17.4 | Dependencias, supply chain, infraestructura, correo, push, logs y configuración productiva | Pendiente |
| 17. Hardening de seguridad | 17.5 | Pruebas ofensivas, remediación, regresión de vulnerabilidades y gate formal de seguridad | Pendiente |
| 18. QA integral V2 | 18.1 | Gate técnico integral de backend, frontend, PostgreSQL, Alembic, OpenAPI y build | Pendiente |
| 18. QA integral V2 | 18.2 | QA E2E de usuario Personal, Workspaces Shared, colaboración, privacidad y casos límite | Pendiente |
| 18. QA integral V2 | 18.3 | QA desktop, móvil, PWA, responsive, accesibilidad y navegadores objetivo | Pendiente |
| 18. QA integral V2 | 18.4 | Corrección de defectos, regresión completa y gate funcional LifeManager V2.0.0 | Pendiente |
| 19. Publicación V2.0.0 | 19.1 | Release candidate, documentación final, estrategia de datos y preparación del despliegue | Pendiente |
| 19. Publicación V2.0.0 | 19.2 | Despliegue controlado de infraestructura, backend, esquema PostgreSQL y frontend/PWA | Pendiente |
| 19. Publicación V2.0.0 | 19.3 | Configuración productiva de secretos, dominios, HTTPS, correo, push y servicios externos | Pendiente |
| 19. Publicación V2.0.0 | 19.4 | Smoke tests, pruebas de seguridad y QA final sobre producción | Pendiente |
| 19. Publicación V2.0.0 | 19.5 | Release oficial LifeManager V2.0.0 e inicio autorizado de datos reales | Pendiente |

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
