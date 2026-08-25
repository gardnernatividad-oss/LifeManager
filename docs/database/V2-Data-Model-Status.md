# Estado del modelo de datos de LifeManager V2.0.0

## Estado

Implementado en el model layer SQLAlchemy y en la revisión Alembic guardada
`e4f5a6b7c8d9`. La metadata registra las 25 tablas de dominio V2 aprobadas.
Stage 2.9 añadió la revisión preservadora `c3d172b18308`, posterior a
`e4f5a6b7c8d9`, y la tabla técnica `rate_limit_buckets`; el head actual es
`c3d172b18308`.

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

## Estado de aplicación

### Persistencia técnica de rate limiting

`rate_limit_buckets` implementa ventanas fijas compartidas entre procesos. Su
clave primaria compuesta es `(action, dimension, key_digest, window_start)`;
almacena únicamente digest HMAC de 32 bytes, contador, inicio y expiración de
ventana. No persiste IP, email, actor ni token en claro. El índice
`ix_rate_limit_buckets_expires_at` soporta limpieza oportunista. Es una tabla
efímera de seguridad, no una entidad de negocio ni historial de auditoría.

- La infraestructura de fixtures V2 y el dataset canónico multi-Workspace están implementados exclusivamente para pruebas y desarrollo local.
- Stage 3.1 implementó la frontera de servicio/autorización Workspace sin modificar la forma física: resolución por Workspace+membresía `ACTIVE`, autoridad de owner derivada y guardas Personal para miembros, eliminación, conversión, transferencia y finalización de la membresía propietaria.
- No existe todavía una API funcional V2 de Workspace; creación Shared, invitaciones y administración de membresías pertenecen a etapas posteriores.
- El runtime y los tests de dominio V1 que importan símbolos retirados son temporalmente incompatibles y serán reemplazados por los verticales V2; no deben interpretarse como defectos del esquema V2.

Este archivo evita que el modelo V1 o documentos históricos se utilicen accidentalmente como diseño físico V2.
