# Contexto de LifeManager

## Estado del producto

LifeManager V1.0.0 es la implementación publicada y la línea base técnica. El tag anotado `v1.0.0` resuelve al commit `fafa8844f83763c837aa423d0773cd6d5782752c`.

LifeManager V2.0.0 está en preparación. Su comportamiento aprobado está documentado en `docs/requirements/Functional-V2.md` y ADR-007; todavía no está implementado.

## Fuentes de autoridad

| Alcance | Fuente |
|---|---|
| Runtime y comportamiento V1 actual | Código en el tag `v1.0.0`, `docs/requirements/Functional.md`, ADR-005 y ADR-006 |
| Modelo físico V1 actual | `docs/database/V1-Target-Data-Model.md` y `docs/database/ERD.md` |
| Objetivo funcional V2 aprobado | `docs/requirements/Functional-V2.md` y ADR-007 |
| Futuro no aprobado | `docs/requirements/FutureIdeas.md`, cuando se documente expresamente como idea |

En caso de contradicción sobre V2, prevalecen `Functional-V2.md` y ADR-007. Ningún documento V2 implica que el runtime actual ya tenga esa capacidad.

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

Los datos V1 existentes son de prueba/no esenciales. Puede diseñarse un reset controlado para V2, pero no se ha autorizado ni ejecutado. Las migraciones históricas y el historial Git no se editan. Tras publicar V2 y comenzar uso real, toda evolución deberá preservar datos de producción.

La siguiente etapa aprobada es Phase 1 — V2 Preparation, Stage 1.3 — Inventory of V1 components that are reusable, modifiable, or replaceable. La arquitectura y el modelo físico V2 se diseñarán después de clasificar primero los componentes V1.

## Principios

- Distinguir implementación actual de objetivo futuro.
- Autorizar siempre en servidor y aislar por Workspace.
- Mantener historia operativa salvo excepciones explícitas.
- Usar terminología española aprobada en la interfaz.
- Diseñar primero para móvil vertical sin degradar desktop.
- Tratar seguridad como requisito transversal, no como etapa opcional final.
