# Gate de seguridad y autorización de Pendientes V2

## Decisión

Stage 6.4: **PASS**. Fase 6 — Pendientes: **CLOSED**. No quedan hallazgos HIGH
abiertos en esta vertical.

## Matriz de acceso

Una cuenta, Workspace y membership `ACTIVE` permiten crear, listar, consultar,
editar, registrar avance o comentario, finalizar, corregir explícitamente,
desactivar, reactivar, eliminar cuando el avance actual es cero y leer historia.
Esto aplica por igual a owner Personal, owner Shared, member Shared,
Responsable y miembro no Responsable. El lifecycle y las capacidades
server-side siguen siendo obligatorios.

Anónimo, cuenta `DISABLED`, Workspace `INACTIVE`, membership `LEFT` o `REMOVED`,
no miembro y `GLOBAL_ADMIN` sin membership quedan denegados. Owner no obtiene
privilegio especial de Pendiente. Todo identificador se resuelve dentro del
Workspace; un recurso ausente o externo no revela datos.

## Invariantes validados

- Estado deriva de avance; Vigencia permanece independiente.
- Finalizar fija fecha local, crea un solo `TRACKING` y deja el registro
  read-only sin desactivarlo.
- La corrección explícita reabre, limpia la fecha de cumplimiento, crea
  `CORRECTION` y preserva la historia previa.
- Comentario-only y cambio de avance crean exactamente una entrada append-only.
- Cumplimiento y diferencia de días son proyecciones, no columnas persistidas.
- Hard delete se revalida bajo lock con avance cero; elimina solo la historia
  dependiente por `CASCADE`. La FK del actor permanece `RESTRICT`.
- DTOs estrictos bloquean mass assignment de Workspace, actores, historia,
  timestamps, campos derivados, roles, capacidades y bypass de versión.
- `SELECT FOR UPDATE` y `lock_version` impiden sobrescrituras silenciosas,
  historia parcial y duplicados ante escrituras concurrentes.
- Listado, filtros, paginación, detalle e historia están aislados por Workspace;
  logout elimina la caché privada.

## Evidencia del gate

Tests enfocados de schemas, services, rutas, Workspace authorization, frontend
y PostgreSQL desechable cubren lifecycle, historial, filtros, IDOR, DTOs,
concurrencia, migración reversible y FKs. La superficie OpenAPI no publica CRUD
genérico ni mutaciones directas de historia.
