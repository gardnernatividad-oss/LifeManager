# Estado del modelo de datos de LifeManager V2.0.0

## Estado

Implementado en el model layer SQLAlchemy y en la revisión Alembic guardada
`e4f5a6b7c8d9`. La metadata registra las 25 tablas V2 aprobadas.

`docs/requirements/Functional-V2.md` y ADR-007 definen el objetivo funcional. `V2-Target-Data-Model.md`, `V2-ERD.md` y ADR-008 fijan el diseño lógico/físico implementado. `V2-Transition-Implementation-Plan.md` fija la transición destructiva controlada, el orden de implementación y las salvaguardas. El esquema V1 permanece documentado en `V1-Target-Data-Model.md` y `ERD.md` como baseline histórico.

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
- Los datos V1 actuales son descartables y la estrategia de reset V2 está implementada únicamente para bases locales/test verificadas.
- La revisión `e4f5a6b7c8d9`, posterior a `d3e4f5a6b7c8`, exige opt-in, entorno seguro, host loopback, nombre allowlisted y forma V1 exacta antes de eliminar objetos.
- La revisión contiene una instantánea local e inmutable de las 25 tablas, valores enum, constraints, índices, defaults y objetos PostgreSQL V2. No importa ni recorre la metadata mutable de `app.models`; cambios futuros del model layer requieren revisiones nuevas.
- La cadena base→V2, la forma final de 25 tablas, los triggers de integridad y el rechazo deliberado de downgrade se validaron en una base PostgreSQL local efímera.
- La paridad entre la instantánea de migración y la metadata V2 vigente se validó localmente por introspección de tablas, columnas, nulabilidad, constraints, índices, funciones y triggers.
- Después de publicar V2, los datos reales deberán preservarse mediante migraciones seguras.

Este archivo evita que el modelo V1 o documentos históricos se utilicen accidentalmente como diseño físico V2.
