# Contexto de LifeManager

## Producto objetivo

LifeManager V1 es una PWA personal para planificar, revisar, seguir y analizar Tareas, Pendientes y Proyectos dentro del Personal Workspace del usuario.

La especificación autoritativa es `docs/requirements/Functional.md`; la decisión vigente es ADR-005.

## Alcance V1

- Registro/login y perfil.
- Creación automática de un único Workspace `Personal` y membresía OWNER.
- Tablas maestras de Categorías y Tareas.
- Planificación, Revisión, Seguimiento y Reportes separados.
- Tareas fechadas, Pendientes porcentuales y Proyectos con Pasos ponderados.
- Inicio operativo compacto.
- Configuración limitada a perfil y zona horaria.
- PWA responsive en español.

## Arquitectura técnica

- Backend: FastAPI, SQLAlchemy 2.x, Alembic y PostgreSQL.
- Frontend: React, TypeScript, Vite, TanStack Query, Axios, React Hook Form y Zod.
- Autenticación mediante Bearer JWT.
- UUID en entidades y aislamiento de recursos por `workspace_id`.

El backend conserva una arquitectura multi-workspace capaz de evolucionar hacia V2. V1 no expone esa capacidad en la interfaz.

## Estado actual frente al objetivo

La aplicación existente implementa una base funcional amplia, pero refleja decisiones previas: TaskSeries persistente, Daily Form/Workflow, estados y settings ampliados, múltiples workspaces seleccionables y módulos frontend reorganizados de otra manera. Estos componentes no prueban el diseño objetivo y deberán refactorizarse incrementalmente.

No se deben editar migraciones históricas. Los cambios de datos requieren migraciones nuevas, backfill explícito, compatibilidad temporal cuando sea necesaria y pruebas de aislamiento/historial.

## Principios

- Claridad semántica antes que reutilización accidental.
- Historial preservado.
- Datos maestros inmutables después de uso.
- Estados derivados cuando corresponda.
- Separación entre Planificación, Revisión, Seguimiento y Reportes.
- Interfaz compacta, accesible y responsive.
- No presentar una función heredada como parte de V1 si contradice la especificación.

## Fuera de alcance

Calendario/Actividades, colaboración, invitaciones, workspaces adicionales, notificaciones, recordatorios, Notes, Goals, Finance, integraciones, administración avanzada, hábitos independientes y recurrencia perpetua.
