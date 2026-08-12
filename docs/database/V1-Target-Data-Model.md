# Modelo de datos objetivo de LifeManager V1

## Estado

Pendiente de diseño físico.

ADR-005 y `docs/requirements/Functional.md` definen el objetivo funcional autoritativo de LifeManager V1 — Personal Workspace. Este documento reserva la ubicación canónica del futuro modelo físico, pero todavía no define tablas, columnas, claves, enums, restricciones ni relaciones de implementación.

## Próxima etapa de diseño

La siguiente etapa deberá diseñar explícitamente el esquema para:

- User;
- Personal Workspace;
- Category;
- Master Task;
- Task occurrence;
- Pending Item;
- Project;
- Project Step;
- metadatos y timestamps de Revisión y Seguimiento.

El diseño deberá traducir las reglas funcionales aprobadas sin reintroducir conceptos del modelo legado por conveniencia técnica.

## Restricciones para el próximo diseño

1. No se diseñará ninguna migración nueva a partir del modelo legado.
2. El historial existente de Alembic permanecerá intacto.
3. La transición deberá preservar datos e integridad histórica.
4. Toda entidad de negocio deberá mantener aislamiento por Personal Workspace.
5. Las relaciones, estados almacenados/derivados, reglas de inmutabilidad y estrategia de backfill deberán aprobarse antes de implementar migraciones.
6. El modelo físico deberá distinguir claramente Tarea maestra, ocurrencia de Tarea, Pendiente, Proyecto y Paso de proyecto.

## Documento histórico

El diseño físico anterior se conserva únicamente como registro reemplazado en:

`docs/database/Legacy-V1-Target-Data-Model.md`

Ese documento no es una fuente de implementación para V1.
