# ADR-006: Modelo físico de datos V1

## Estado

Aceptado como modelo físico V1. No define el esquema V2; para su objetivo funcional prevalece ADR-007.

## Fecha

2026-08-11

## Contexto

ADR-005 aprobó el diseño funcional del Personal Workspace. Era necesario traducirlo a un objetivo físico sin reutilizar el modelo legado incompatible.

## Decisión

- Se mantienen UUID, User, Workspace y WorkspaceMember.
- Workspace recibe `kind`; V1 crea uno `PERSONAL` mediante service, sin prohibir Workspaces V2.
- Category y MasterTask usan nombres normalizados únicos por Workspace y se vuelven inmutables al ser referenciados; no almacenan un flag mutable de uso.
- Task referencia MasterTask, persiste fecha y resultado terminal nullable; Programada/Pendiente son derivados.
- Se prohíbe el duplicado `(workspace_id, master_task_id, planned_date)`.
- La creación masiva no tiene entidad/procedencia persistida.
- PendingItem conserva solo avance/comentario actuales.
- Project se compone exclusivamente de ProjectStep; progreso, fecha y estado son derivados.
- Los timestamps de Revisión/Pendientes viven en una tabla 1:1 de metadata del Workspace; cada Project conserva su timestamp de tracking. `last_review_saved_at` es Workspace-level solo por la cardinalidad personal de V1 y deberá reevaluarse antes de colaboración V2, probablemente mediante metadata por `workspace_member`. El timestamp de Pendientes puede seguir representando el último guardado del registro compartido, sujeto también a revisión V2.
- Los batches son atómicos y usan `lock_version` para concurrencia optimista.
- Relaciones críticas usan FK compuestas conscientes del Workspace; ProjectStep hereda scope mediante Project.
- Task result usa VARCHAR + check; Vigencia usa boolean; valores derivados no se persisten.

## Consecuencias

El modelo reduce redundancia y protege historia, pero exige services para inmutabilidad, activación de Proyectos, suma transversal de pesos y reglas de borrado. La base heredada necesitará una auditoría y migraciones incrementales posteriores; no se modifica el historial Alembic.

## Documento detallado

`docs/database/V1-Target-Data-Model.md`.
