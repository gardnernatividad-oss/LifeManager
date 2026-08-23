# Estado del modelo de datos de LifeManager V2.0.0

## Estado

Pendiente de diseño técnico.

`docs/requirements/Functional-V2.md` y ADR-007 definen el objetivo funcional, pero no fijan tablas, columnas, enums, FKs, índices ni migraciones V2. El esquema V1 actual permanece documentado en `V1-Target-Data-Model.md` y `ERD.md`.

## Capacidades que el diseño deberá resolver

- Workspaces compartidos, membresías y roles globales separados.
- Responsables en Tareas, Pendientes y Etapas.
- Unicidad de Tarea por catálogo, fecha y Responsable.
- Catálogo y ocurrencias de Actividades.
- Organizador, Participantes y retiro individual de Calendario.
- Recurrencia finita diaria, semanal y mensual con deduplicación.
- Privacidad de calendario consolidado por Workspace compartido.
- Historia cronológica de Pendientes y Etapas.
- Notificaciones, preferencias y trazabilidad necesaria.
- Inmutabilidad histórica y reclasificación dinámica aprobada.
- Retiro de miembros sin reescribir el pasado.

## Restricciones de transición

- No se editará el historial Alembic existente.
- Los datos V1 actuales son descartables para desarrollo, pero ningún reset está autorizado en la etapa documental.
- Antes de implementar se aprobarán modelo físico, estrategia de transición, aislamiento, autorización y pruebas.
- Después de publicar V2, los datos reales deberán preservarse mediante migraciones seguras.

Este archivo evita que el modelo V1 o documentos históricos se utilicen accidentalmente como diseño físico V2; no anticipa una solución.
