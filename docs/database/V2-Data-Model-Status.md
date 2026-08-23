# Estado del modelo de datos de LifeManager V2.0.0

## Estado

Diseñado y aprobado documentalmente; no implementado.

`docs/requirements/Functional-V2.md` y ADR-007 definen el objetivo funcional. `V2-Target-Data-Model.md`, `V2-ERD.md` y ADR-008 fijan el diseño lógico/físico para implementación futura. `V2-Transition-Implementation-Plan.md` fija la transición destructiva controlada, el orden de implementación y las salvaguardas. El esquema V1 actual permanece documentado en `V1-Target-Data-Model.md` y `ERD.md`.

## Capacidades resueltas por el diseño

- Estados exclusivos de cuenta, administración global, auditoría y tokens de acción seguros.
- Workspaces compartidos, membresías y roles globales separados.
- Invitaciones, transferencia de propiedad y lifecycle histórico de membresía.
- Responsables en Tareas, Pendientes y Etapas.
- Unicidad de Tarea por catálogo, fecha y Responsable.
- Catálogo y ocurrencias de Actividades.
- Organizador, Participantes y retiro individual de Calendario.
- Recurrencia finita diaria, semanal y mensual con deduplicación.
- Privacidad de calendario consolidado por Workspace compartido.
- Historia cronológica de Pendientes y Etapas.
- Notificaciones, preferencias y trazabilidad necesaria.
- Suscripciones Web Push y estado de entrega.
- Inmutabilidad histórica y reclasificación dinámica aprobada.
- Retiro de miembros sin reescribir el pasado.

## Restricciones de transición e implementación

- No se editará el historial Alembic existente.
- Los datos V1 actuales son descartables y la estrategia de reset V2 está aprobada únicamente antes del uso real; esta etapa documental no autoriza ejecutarla.
- La transición se implementará mediante una revisión Alembic nueva después de `d3e4f5a6b7c8`; este documento no autoriza crearla ni ejecutarla.
- Después de publicar V2, los datos reales deberán preservarse mediante migraciones seguras.

Este archivo evita que el modelo V1 o documentos históricos se utilicen accidentalmente como diseño físico V2.
