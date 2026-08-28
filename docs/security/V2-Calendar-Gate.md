# Gate de seguridad V2 — Calendario y Actividades

## Estado

Stage 8.5 cierra Phase 8. El gate valida los contratos implementados en Stages
8.1–8.4 y la gestión segura de ocurrencias recurrentes, sin cambiar el esquema
físico ni convertir `GenerationBatch` en una serie mutable.

## Autoridad y frontera histórica

| Actor | Activity futura | En curso o pasada |
|---|---|---|
| Miembro `ACTIVE` del mismo Workspace `ACTIVE` | Crear, consultar, editar y eliminar en Personal o cancelar en Shared | Solo lectura |
| Organizador u owner con membership `ACTIVE` | Misma autoridad, sin privilegio adicional | Solo lectura |
| Participante `ACTIVE` | Puede retirar únicamente su propia participación futura | Solo lectura |
| Anónimo, `LEFT`, `REMOVED`, no miembro o cuenta `DISABLED` | Sin acceso | Sin acceso privado restaurado |
| `GLOBAL_ADMIN` sin membership | Sin bypass | Sin bypass |

`starts_at` es la frontera autoritativa y se revalida bajo lock. Los UUID de
otro Workspace se ocultan como recurso inexistente.

## Ocurrencias y concurrencia

- `THIS` bloquea y modifica solo la ocurrencia seleccionada.
- `THIS_AND_FUTURE` deriva el batch desde la Activity, bloquea batch y
  ocurrencias en orden determinista y alcanza solo filas `SCHEDULED` futuras.
- El scope futuro conserva fechas e historia; puede propagar hora/duración
  local, catálogo, Organizador y Participantes.
- La versión esperada de la ocurrencia seleccionada y los locks serializan
  scopes concurrentes. Las constraints de identidad convierten colisiones en
  `409` y la transacción evita resultados parciales.
- Personal elimina físicamente; Shared persiste `CANCELLED` con actor y
  timestamp. Cancelar excluye la Activity del calendario operacional y
  desactiva recordatorios asociados.
- El retiro propio desactiva únicamente los recordatorios del actor para las
  ocurrencias alcanzadas; no altera a otros Participantes ni historia.

## Privacidad e integración

Las mutaciones invalidan la lista Workspace-scoped, Mi calendario y las
comparaciones afectadas. La comparación conserva `SHOW_DETAILS`,
`AVAILABILITY_ONLY` y `HIDE`; nunca concede acceso al Workspace de origen ni
expone detalles dentro de bloques opacos.

## Evidencia

El gate incluye DTO/OpenAPI, servicios, rutas, PostgreSQL desechable,
concurrencia, identidad, lifecycle Personal/Shared, aislamiento de
Participantes/recordatorios, frontend responsive, cache, TypeScript, ESLint y
build PWA. No se contactó `lifemanager`, remoto ni producción.
