# Trazabilidad de la reorganización del Roadmap V2

## Propósito

Este documento demuestra que la reorganización aplicada después de Stage 3.3
solo cambia la granularidad del trabajo pendiente. No elimina funcionalidad, no
traslada alcance a V3 y no modifica la historia completada.

Fuentes de alcance: `Functional-V2.md`, `NonFunctional.md`, arquitectura,
permisos, modelo físico V2, contrato API, navegación, inventario de pantallas,
sistema de diseño, ADRs V2, threat model y documentación de publicación.

## Baseline histórico comprobable

En el `HEAD` inmediatamente anterior a esta reorganización había **0 filas
Pendiente** en `Roadmap.md`. La historia Git conserva 15 filas que alguna vez
estuvieron pendientes: Stages 1.2, 1.3, 1.4 y 2.2–2.13; todas están hoy
legítimamente `Completado` y no se remapean como trabajo futuro. Ese Roadmap
intermedio, sin embargo, omitía seis bloques completados acreditados por otras
fuentes: Phase 0 completa (0.1–0.5) y Stage 1.7.

Stage 3.3 no existió como fila pendiente en un commit: su implementación se
comprometió y la fila se incorporó directamente como `Completado`. Por ello, la
antigua necesidad “invitaciones Shared” se asigna a **Stage 3.3 completado**, no
se duplica en el consolidado pendiente.

No existía en Git una tabla de micro-stages futuros que pudiera copiarse fila
por fila. Para evitar inventar identificadores históricos, las tablas siguientes
trazan cada bloque nuevo contra los requisitos autoritativos que absorbe.

## Historia completada preservada

La búsqueda de todas las versiones Git de `Roadmap.md` encontró estas filas que
alguna vez estuvieron pendientes. Su destino es su mismo stage hoy completado;
no deben reaparecer dentro de los 60 bloques futuros.

| Antigua fila pendiente | Destino actual |
|---|---|
| Stage 1.2 — Update and consolidate V2 functional documentation | Stage 1.2 — Completado |
| Stage 1.3 — Inventory of V1 components that are reusable, modifiable, or replaceable | Stage 1.3 — Completado |
| Stage 1.4 — Design of the V2 logical and physical data model | Stage 1.4 — Completado |
| Stage 2.2 — Secrets and configuration audit | Stage 2.2 — Completado |
| Stage 2.3 — Global roles and account state | Stage 2.3 — Completado |
| Stage 2.4 — Registration and approval | Stage 2.4 — Completado |
| Stage 2.5 — Email verification | Stage 2.5 — Completado |
| Stage 2.6 — Password recovery | Stage 2.6 — Completado |
| Stage 2.7 — Password policy and hashing | Stage 2.7 — Completado |
| Stage 2.8 — Session architecture | Stage 2.8 — Completado |
| Stage 2.9 — Rate limiting and brute-force protection | Stage 2.9 — Completado |
| Stage 2.10 — Turnstile integration | Stage 2.10 — Completado |
| Stage 2.11 — Server validation and error handling | Stage 2.11 — Completado |
| Stage 2.12 — Security tests | Stage 2.12 — Completado |
| Stage 2.13 — Identity and security gate | Stage 2.13 — Completado |
| Necesidad histórica: invitaciones a Workspace Compartido | Stage 3.3 — Completado |

Los demás stages de Phase 1, Phase 2 y 3.1–3.2 también permanecen completados;
no tuvieron una versión `Pendiente` rastreable que requiera remapeo.

### Seis filas completadas reconciliadas

| Fila restaurada | Evidencia de repositorio | Motivo de la ausencia intermedia |
|---|---|---|
| 0.1 — Definición del alcance funcional de LifeManager V2.0.0 | `Functional-V2.md`, ADR-007 y commit `90bc7f2` | El Roadmap técnico comenzó en Phase 1 y omitió la fase funcional previa |
| 0.2 — Navegación, terminología y arquitectura de información V2 | `Navigation.md`, Glossary, Functional‑V2 y `90bc7f2` | Mismo corte técnico intermedio |
| 0.3 — Inventario de pantallas y flujos funcionales V2 | `Screens.md`, Functional‑V2 y `90bc7f2` | Mismo corte técnico intermedio |
| 0.4 — Sistema de diseño, componentes y criterios responsive | `DesignSystem.md`, `Components.md`, NonFunctional y `90bc7f2` | Mismo corte técnico intermedio |
| 0.5 — Consolidación y aprobación de la línea base funcional V2 | ADR‑007 aceptado y commit `90bc7f2` | La aprobación quedó documentada, pero no como fila canónica |
| 1.7 — Estrategia de reset de datos V1 y transición del esquema a V2 | `V2-Transition-Implementation-Plan.md`, `Migrations.md`, ADR‑008, commit `18e004c` y safeguards de `e4f5a6b7c8d9` | Omisión de numeración entre 1.6 y 1.8 |

## Auditoría de numeración

No se encontraron duplicados actuales. Los identificadores 1.10 y 2.10 se
preservan con sus nombres y posición correctos; no se confunden con 1.1 o 2.1.
Stage 1.7 se restaura entre 1.6 y 1.8 con respaldo documental, y se añaden
3.4–18.5 según el consolidado aprobado.

## Trazabilidad del alcance pendiente consolidado

### 3. Workspaces y colaboración base

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 3.4 | Listar miembros; lifecycle ACTIVE/LEFT/REMOVED; salida voluntaria; retiro por owner; preservar historia; cortar acceso inmediatamente; reingreso mediante invitación nueva; privacidad inicial segura. |
| 3.5 | Transferencia de propiedad con locks; prohibición de salida del owner; eliminación Shared controlada; análisis/reasignación o eliminación de Tareas, Pendientes, Etapas y Activities futuras; `Eliminar todo`; conservación histórica. |
| 3.6 | Listado y selector multi-Workspace; rol visible derivado Propietario/Miembro; integración de scopes globales y por Workspace; permisos reutilizables; separación estricta de `GLOBAL_ADMIN`. |
| 3.7 | Matrices owner/member/nonmember/admin; IDOR, concurrencia, lifecycle, aislamiento, Personal invariants, PostgreSQL y gate funcional Workspace. |

### 4. Tablas maestras

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 4.1 | Category, MasterTask y ActivityMaster; normalización Unicode; unicidad por Workspace; alta y edición; relaciones y aislamiento. |
| 4.2 | ACTIVE/INACTIVE; inmutabilidad o reclasificación explícita tras uso; preservación de historia; selectores reutilizables; bloqueo concurrente del primer uso y referencias RESTRICT. |
| 4.3 | Pantallas compactas y responsive de Tablas; errores y conflictos seguros; autorización; tests unitarios/PostgreSQL/E2E y gate. |

### 5. Tareas

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 5.1 | Crear, editar y eliminar Tareas elegibles; fecha `DATE`; MasterTask/categoría derivados; Responsable miembro ACTIVE; resultados y resolución; Planning versus Tracking; optimistic locking. |
| 5.2 | Recurrencia finita diaria, semanal y mensual; weekdays; start/end obligatorios; generación material inmediata e idempotente; unicidad; 29/30/31 con último día; febrero y deduplicación de colisiones. |
| 5.3 | Solo esta/Todas las futuras; GenerationBatch sin serie mutable; cambios y eliminación futura; listados, filtros, orden, paginación y UI responsive/mobile-first. |
| 5.4 | Autorización por Workspace/Responsable, mass assignment, concurrencia, aislamiento, historia, pruebas PostgreSQL/API/frontend y gate. |

### 6. Pendientes

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 6.1 | Planning, ACTIVE/INACTIVE, planned date coherente, Responsable, progreso 0–100, cumplimiento temporal, correcciones permitidas y tracking atómico. |
| 6.2 | PendingItemHistory inmutable, comentarios, actores, timestamps, detalle, progreso y cumplimiento histórico. |
| 6.3 | Registro completo, filtros, fechas, vigencia, paginación, detalle y edición responsive/mobile-first. |
| 6.4 | Workspace isolation, membresía ACTIVE, locking, conflicto optimista, pruebas de historia/atomicidad y gate. |

### 7. Proyectos y Etapas

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 7.1 | CRUD/lifecycle de Project, categoría, Líder miembro ACTIVE, fechas, estado general y transferencia/retiro de liderazgo. |
| 7.2 | ProjectStage, Responsable, posición, pesos, suma de pesos, progreso, cumplimiento, tracking atómico y locking. |
| 7.3 | Historial de Líder y Etapas, comentarios, autoría, navegación Proyecto → Etapa y conservación histórica. |
| 7.4 | UI desktop/mobile, permisos, aislamiento, concurrencia, PostgreSQL, frontend y gate completo. |

### 8. Calendario y Actividades

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 8.1 | ActivityMaster o Activity personalizada, Workspace, organizador, participantes, estados y retiro individual; horas zonificadas reproducibles. |
| 8.2 | Recurrencia finita de Activities, GenerationBatch, Solo esta/Todas las futuras, recordatorios por participante/organizador y modificaciones seguras de series. |
| 8.3 | Mi calendario global consolidado, colores por Workspace, vistas semanal desktop y diaria móvil, navegación y detalle responsive. |
| 8.4 | SHOW_DETAILS/AVAILABILITY_ONLY/HIDE; calendario consolidado por persona; comparación diaria de disponibilidad sin filtrar detalles privados. |
| 8.5 | Organizador/participante, aislamiento, DST/timezone, privacidad, concurrencia, pruebas frontend/backend/PostgreSQL y gate. |

### 9. Revisión

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 9.1 | Motor global entre Workspaces; tres bloques Tareas/Pendientes/Etapas; elegibilidad `<= hoy`; vigencia ACTIVE y reglas de selección. |
| 9.2 | Guardados independientes por bloque, atomicidad interna, timestamps de última revisión y experiencia mobile-first. |
| 9.3 | Autorización, aislamiento, locking determinístico, concurrencia, pruebas y gate de Revisión. |

### 10. Inicio

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 10.1 | Inicio global, resumen diario accionable, próximos/vencidos, Workspaces pertinentes y accesos rápidos sin duplicar Seguimiento/Reportes. |
| 10.2 | Estados loading/error/empty, responsive, accesibilidad, agregaciones eficientes, pruebas y gate. |

### 11. Notificaciones y recordatorios

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 11.1 | Eventos tipados, campana overlay, Notification, push subscriptions/deliveries, scheduler idempotente, retries y retención. |
| 11.2 | Resumen diario, recordatorio de Revisión y seguimientos Pending/Project configurables por usuario. |
| 11.3 | Recordatorios de Activities, cambios/cancelaciones, una notificación lógica por serie, agrupación y deep links. |
| 11.4 | Consentimiento, privacidad, claves, abuso, jobs autenticados, pruebas de entrega/retry y gate. |

### 12. Reportes

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 12.1 | Infraestructura común, periodos abiertos/cerrados, filtros, agregaciones SQL, aislamiento y contratos estables. |
| 12.2 | Resultados de Tareas; avance/cumplimiento de Pendientes; progreso de Proyectos y cumplimiento de Etapas. |
| 12.3 | Reportes de Activities, recurrencia/participación y reclasificación histórica explícita sin reescribir historia silenciosamente. |
| 12.4 | Tablas/gráficos aprobados, responsive, accesibilidad, autorización, rendimiento, pruebas y gate. |

### 13. Configuración

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 13.1 | Perfil, timezone IANA, estructura general Spanish-first, convenciones de fecha y preferencias comunes. |
| 13.2 | Preferencias de recordatorios/seguimientos y privacidad de Calendario por membresía. |
| 13.3 | Gestión visible de Workspaces/membresías, seguridad de cuenta y Acerca de/versión, respetando fronteras globales. |
| 13.4 | Responsive, accesibilidad, permisos, validación, pruebas y gate de Configuración. |

### 14. Administración global

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 14.1 | Consola privada GLOBAL_ADMIN, solicitudes/cuentas, estados, auditoría operativa y administración estrictamente de plataforma. |
| 14.2 | No acceso implícito a contenido, mass assignment, auditoría, seguridad, pruebas negativas y gate administrativo. |

### 15. Integración UX y PWA

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 15.1 | Navegación final, layouts, patrones comunes, estados de consulta/mutación, diseño compacto y coherencia visual. |
| 15.2 | Auditoría desktop/móvil, mobile-first, teclado, foco, lectores de pantalla, contraste y targets táctiles. |
| 15.3 | Manifest/service worker, offline shell, caché sin datos privados obsoletos, actualización segura y gate PWA. |

### 16. Hardening de seguridad

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 16.1 | Threat model final, inventario de superficie, secretos, bundles, historial y configuración productiva. |
| 16.2 | Sesión/cookies/CSRF, cuentas, roles, autorización, IDOR, aislamiento Workspace y privacidad final. |
| 16.3 | SQL/injection, XSS, validación, envelopes, CORS, CSP, headers, navegador y exposición OpenAPI. |
| 16.4 | Dependencias/supply chain, Render/Cloudflare/Neon, email, push, scheduler, rotación y operación segura. |
| 16.5 | Matrices ofensivas, concurrencia, abuso, remediación, regresión y gate formal sin hallazgos HIGH/CRITICAL abiertos. |

### 17. QA integral V2

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 17.1 | Suites backend/frontend, compile/typecheck/lint/build, Alembic base→head y gates PostgreSQL. |
| 17.2 | E2E Personal/Shared, multiusuario, invitaciones, lifecycle, recurrencia, Review, Calendar y casos límite. |
| 17.3 | Desktop, móvil, PWA, instalación/offline shell, accesibilidad y navegadores objetivo. |
| 17.4 | Triage/corrección, regresión completa, documentación de evidencia y gate funcional V2.0.0. |

### 18. Publicación V2.0.0

| Stage | Requisitos y trabajo absorbidos |
|---|---|
| 18.1 | Release candidate, changelog/documentación, backups, plan de datos, rollback y checklist. |
| 18.2 | Despliegue de infraestructura, backend Render, esquema Neon y frontend/PWA Cloudflare. |
| 18.3 | Secretos únicos, dominios, HTTPS, CORS/CSP, email, push, jobs y observabilidad productiva. |
| 18.4 | Smoke test, migraciones verificadas, seguridad, flujos críticos y QA final en producción. |
| 18.5 | Tag/release oficial `v2.0.0`, inicio de datos reales, backups y cambio a migraciones preservadoras. |

## Matriz de cobertura transversal

| Requisito crítico | Stage destino |
|---|---|
| Membresía, salida/retiro, transferencia, responsabilidades futuras, selector y aislamiento | 3.4–3.7 |
| Category, MasterTask, ActivityMaster, lifecycle, reclasificación y selectores | 4.1–4.3 |
| Recurrencia diaria/semanal/mensual, 29/30/31, febrero, dedupe y unicidad | 5.2–5.3 |
| Historias Pending y ProjectStage, comentarios, pesos y cumplimiento | 6.2, 7.2–7.3 |
| Organizer, participants, recurrencia, reminders, privacidad y comparación | 8.1–8.5 |
| Tres bloques de Review, `<= hoy` y guardados independientes | 9.1–9.3 |
| Campana, push, reminders, seguimientos, agrupación y deep links | 11.1–11.4 |
| Reportes de cuatro dominios, filtros y reclasificación | 12.1–12.4 |
| Configuración, administración, UX/PWA, seguridad, QA y publicación | 13.1–18.5 |

## Resultado de trazabilidad

- Stages completados reconciliados: **32** (5 de Phase 0, 11 de Phase 1,
  13 de Phase 2 y 3 de Phase 3).
- Filas pendientes antiguas en el baseline inmediato: **0**; no hay huérfanas.
- Filas históricamente pendientes encontradas en Git: **15**; todas se preservan
  como completadas.
- Nuevos stages pendientes: **60**.
- Total canónico: **92**.
- Necesidad histórica de invitaciones: absorbida por Stage 3.3 completado.
- Requisitos externos auditados: todos tienen destino en 3.4–18.5.
- Alcance eliminado o desplazado fuera de V2: **ninguno**.
