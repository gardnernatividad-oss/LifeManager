# ADR-008: Modelo lógico y físico de datos V2

## Estado

Aceptado para implementación futura. No implementado.

## Fecha

2026-08-22

## Contexto

ADR-007 fija el comportamiento funcional V2. Stage 1.3 confirmó que la infraestructura V1 es reutilizable, pero que colaboración, responsables, historia, Calendario, notificaciones y seguridad de cuenta requieren un modelo nuevo. Los datos V1 actuales son descartables antes del uso real de V2.

## Decisión

- `docs/database/V2-Target-Data-Model.md` es el diseño lógico/físico autoritativo V2 y `V2-ERD.md` su vista relacional.
- User conserva identidad global y usa un estado exclusivo de cuenta, rol global separado, auditoría de cambios y tokens de acción almacenados como digest.
- Workspace guarda `owner_user_id` como única autoridad de propiedad. WorkspaceMember representa membresía histórica, no se elimina al salir y no contiene roles V1 ADMIN/VIEWER.
- Las asignaciones y actores de negocio usan FKs compuestas Workspace+User contra WorkspaceMember.
- Category, MasterTask y ActivityMaster son catálogos Active/Inactive; las ocurrencias derivan dinámicamente Category desde su master.
- Task y Activity son ocurrencias materiales. GenerationBatch conserva procedencia finita e inmutable para operaciones futuras, sin restaurar TaskSeries ni sincronización.
- Pendientes y Etapas guardan estado corriente para consulta y eventos históricos append-only para avance/comentario/actor; las reasignaciones de Líder conservan auditoría propia.
- `ProjectStage`/`project_stages` es el nombre técnico V2 recomendado.
- Actividad conserva el nombre como snapshot, deriva Category del master cuando existe y usa Category explícita cuando es custom.
- Calendar availability se deriva; la privacidad vive en WorkspaceMember.
- Revisión usa metadata global por usuario y timestamps independientes por bloque.
- Preferencias de recordatorio se limitan a los cuatro tipos aprobados; Notifications son lógicas y PushSubscription/Delivery separan dispositivo y entrega.
- Se usan UUID, TIMESTAMPTZ, constraints explícitas, enums de aplicación con VARCHAR+CHECK, locking optimista y orden de locks determinístico.
- Se recomienda una nueva migración destructiva controlada V1→V2 después del head, preservando historial Alembic y sin editar revisiones previas.

## Consecuencias positivas

- La integridad de Workspace y asignaciones no depende solo de frontend/services.
- El retiro de miembros no destruye autoría histórica.
- El modelo soporta Revisión global sin compartir timestamps entre personas.
- La recurrencia permite operaciones futuras relacionadas sin convertir un batch en plantilla mutable.
- Historial, reporting y notificaciones tienen fuentes separadas y claras.

## Costos y riesgos

- Las FKs compuestas y el trigger diferible de propiedad requieren migraciones/pruebas PostgreSQL cuidadosas.
- La generación mensual y deduplicación necesitan pruebas calendáricas exhaustivas.
- Histories exigen transacciones que actualicen estado corriente e inserten evento conjuntamente.
- Calendar global y privacidad requieren consultas por rango y autorización rigurosa.
- El reset recomendado es excepcional e irreversible; sus safeguards son obligatorios.

## No decidido por esta ADR

- rutas/payloads API concretos;
- mecanismo final de sesión/token;
- proveedor de correo/push;
- scheduler y workers;
- duración exacta de retención;
- métricas finales de Inicio/Reportes;
- adopción de RLS.

Estas decisiones no alteran la estructura lógica principal y pertenecen a etapas posteriores.
