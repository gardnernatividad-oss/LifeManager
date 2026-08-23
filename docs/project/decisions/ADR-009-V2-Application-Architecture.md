# ADR-009: Arquitectura de aplicación V2

## Estado

Aceptado para implementación futura. No implementado.

## Fecha

2026-08-22

## Contexto

V2 incorpora operaciones multi-dominio, concurrencia optimista, historia inmutable y notificaciones transaccionales. El patrón V1 Router→Service→Session es válido, pero necesita una frontera explícita para coordinación sin commits anidados.

## Decisión

- FastAPI routers permanecen finos y poseen commit/rollback de cada request de escritura.
- Domain services hacen query/add/delete/execute/flush y nunca commit/rollback ni importan FastAPI.
- Un application/orchestration service coordina casos multi-dominio sobre la misma Session; tampoco posee transacción.
- Query services read-only componen agregaciones globales y reportes.
- Domain errors derivan de una jerarquía mínima de aplicación y handlers globales los convierten a respuestas seguras.
- Toda query de recurso Workspace-scoped incluye `workspace_id`; constraints y services comparten la defensa.
- Operaciones concurrentes usan `lock_version`, locking pesimista solo donde corresponde, orden de locks determinístico y constraints como frontera final.
- Cambios de dominio, history y Notification lógica se escriben atómicamente.

La especificación operativa completa está en [`V2-Architecture-Baseline.md`](../../architecture/V2-Architecture-Baseline.md).

## Consecuencias

- No hay commits anidados ni transacciones parcialmente confirmadas.
- Casos simples no adquieren capas artificiales.
- Los routers dejan de duplicar reglas y mapas de excepciones.
- Los tests deben cubrir PostgreSQL/HTTP real además de mocks.

## Reemplazo

ADR-001 permanece como historia de la arquitectura inicial. Para implementación V2, esta ADR y el baseline V2 prevalecen en layering, transacciones, errores y concurrencia.
