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
| Arquitectura técnica V2 aprobada, no implementada | `docs/architecture/V2-Architecture-Baseline.md` y ADR-009–012 |
| Permisos y autorización V2 | `docs/architecture/Permissions.md` y ADR-011 |
| Modelo lógico/físico V2 aprobado, no implementado | `docs/database/V2-Target-Data-Model.md`, `docs/database/V2-ERD.md` y ADR-008 |
| Transición e implementación física V2 aprobadas, no ejecutadas | `docs/database/V2-Transition-Implementation-Plan.md` |
| Contrato API transversal V2, no implementado | `docs/api/V2-Contract-Status.md`, ADR-010 y ADR-011 |
| Seguridad y requisitos no funcionales V2 | `docs/requirements/NonFunctional.md` |
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

Los datos V1 existentes son de prueba/no esenciales. El reset controlado V1→V2 está diseñado y aprobado como estrategia excepcional previa al uso real, pero no se ha creado ni ejecutado. Las migraciones históricas y el historial Git no se editan. Tras publicar V2 y comenzar uso real, los resets destructivos dejan de ser aceptables y toda evolución deberá preservar datos de producción.

La preparación documental V2 ya define baseline funcional, modelo físico, transición desde `d3e4f5a6b7c8` y arquitectura técnica. La siguiente etapa de implementación debe construir primero enums/modelos V2 y sus pruebas de metadata; después debe crear y probar la revisión destructiva controlada, sin ejecutar el reset sobre una base compartida o productiva.

## Principios

- Distinguir implementación actual de objetivo futuro.
- Autorizar siempre en servidor y aislar por Workspace.
- Mantener historia operativa salvo excepciones explícitas.
- Usar terminología española aprobada en la interfaz.
- Diseñar primero para móvil vertical sin degradar desktop.
- Tratar seguridad como requisito transversal, no como etapa opcional final.
