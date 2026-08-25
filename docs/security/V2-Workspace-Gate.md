# Gate de Workspaces V2 — Stage 3.7

## Resultado

Stage 3.7 queda **Completado**. El gate integrado verificó autorización,
aislamiento, lifecycle, concurrencia, contratos y contexto frontend de la
foundation Workspace implementada en Stages 3.1–3.6. No habilita todavía
verticales funcionales V2: cada dominio deberá aplicar su propia matriz sobre
esta frontera común.

## Convenciones de la matriz

- `OK`: operación permitida y limitada al Workspace autorizado.
- `401`: sesión ausente o cuenta no utilizable.
- `403`: identidad válida sin autoridad requerida.
- `404`: Workspace, invitación, miembro o recurso inexistente/ajeno oculto.
- `409`: estado conocido incompatible, sin mutación parcial.
- `EXCLUIDO`: el Workspace no aparece en ese listado.

`GLOBAL_ADMIN sin membership` significa una cuenta `ACTIVE` con rol global,
pero sin membresía en el Workspace objetivo. Ese rol nunca cambia una celda de
Workspace.

## Matriz autoritativa — Workspace Shared ACTIVE

| Operación | Anónimo | Owner Shared ACTIVE | Member Shared ACTIVE | LEFT/REMOVED | No miembro | GLOBAL_ADMIN sin membership | Cuenta DISABLED con membership previa |
|---|---:|---:|---:|---:|---:|---:|---:|
| Listado operacional | 401 | OK, incluido | OK, incluido | EXCLUIDO | EXCLUIDO | EXCLUIDO | 401 |
| Listado de gestión | 401 | OK, incluido | OK, incluido | EXCLUIDO | EXCLUIDO | EXCLUIDO | 401 |
| Crear otro Shared | 401 | OK, como owner del nuevo | OK, como owner del nuevo | OK, como owner del nuevo | OK, como owner del nuevo | OK, sin bypass ajeno | 401 |
| Ver miembros | 401 | OK | OK | 404 | 404 | 404 | 401 |
| Invitar | 401 | OK | 403 | 404 | 404 | 404 | 401 |
| Cancelar invitación | 401 | OK | 404 | 404 | 404 | 404 | 401 |
| Retirar miembro | 401 | OK, objetivo ordinario | 403 | 404 | 404 | 404 | 401 |
| Salir | 401 | 409 | OK | 404 | 404 | 404 | 401 |
| Transferir propiedad | 401 | OK, destino ACTIVE del mismo Workspace | 403 | 404 | 404 | 404 | 401 |
| Resolver responsabilidades para salida/retiro | 401 | OK al retirar; no puede salir | OK al salir | 404 | 404 | 404 | 401 |
| Desactivar | 401 | OK | 403 | 404 | 404 | 404 | 401 |
| Reactivar | 401 | 409, ya está ACTIVE | 403/404 | 404 | 404 | 404 | 401 |
| Hard delete | 401 | OK solo si `can_delete` se revalida verdadero | 403 | 404 | 404 | 404 | 401 |
| Selector/contexto | 401 | OK | OK | EXCLUIDO | EXCLUIDO | EXCLUIDO | 401 |

Aceptar o rechazar una invitación no depende de membership previa: solo la
cuenta `ACTIVE` que es destinataria exacta obtiene `OK`. Otro usuario,
incluido owner, Member o `GLOBAL_ADMIN`, recibe `404`. Una invitación vencida o
ya terminal produce `409`. La cancelación corresponde únicamente al owner del
Workspace Shared ACTIVE.

## Matriz autoritativa — Personal e INACTIVE

| Operación | Personal owner ACTIVE | Otro usuario / GLOBAL_ADMIN sin membership | Shared owner INACTIVE | Member del Shared INACTIVE |
|---|---:|---:|---:|---:|
| Listado operacional/selector | OK | EXCLUIDO | EXCLUIDO | EXCLUIDO |
| Listado de gestión | OK | EXCLUIDO | OK | EXCLUIDO |
| Ver miembros colaborativos | 409 | 404 | 404 | 404 |
| Invitar/cancelar | 409/404 | 404 | 404/409 | 404 |
| Salir/retirar | 409 | 404 | 404 | 404 |
| Transferir | 409 | 404 | 404 | 404 |
| Desactivar | 409 | 404 | 409 | 404 |
| Reactivar | 409 | 404 | OK | 404 |
| Hard delete | 409 | 404 | OK solo vacío y revalidado | 404 |

Personal conserva exactamente un owner con membership `ACTIVE`; no acepta
miembros arbitrarios, invitaciones, transferencia, salida, desactivación ni
hard delete. La unicidad por owner y la membresía del owner tienen enforcement
PostgreSQL además de guardas de servicio.

## Lifecycle, aislamiento y concurrencia

- `ACTIVE → LEFT` y `ACTIVE → REMOVED` reutilizan una sola fila histórica.
- Una invitación nueva permite `LEFT/REMOVED → ACTIVE`, actualiza `joined_at`,
  limpia `ended_at` y restablece `calendar_visibility=HIDE`.
- Toda consulta privada exige cuenta, Workspace y membership `ACTIVE`.
- Los UUID ajenos se resuelven dentro del scope autorizado y no conceden
  enumeración; `GLOBAL_ADMIN` no sustituye membership ni ownership.
- Los DTO son allowlists estrictas: owner, kind, lifecycle, actor, roles,
  membership, auditoría, locks y `can_delete` se derivan en servidor.
- El orden canónico de mutaciones colaborativas es Workspace primero y luego
  memberships, invitaciones o recursos en orden determinista.
- El gate corrigió las invitaciones para volver a bloquear el Workspace antes
  de crear y para bloquear `Workspace → WorkspaceInvitation` al
  aceptar/rechazar/cancelar. Esto evita la inversión frente a desactivación y
  hace que crear una invitación se serialice con el lifecycle.
- Duplicación de invitación, doble aceptación, aceptación contra
  rechazo/cancelación, salida contra retiro y transferencia concurrente tienen
  un único resultado consistente.

## Responsabilidades e historia

La salida y el retiro procesan en una transacción Tareas futuras, Pendientes,
Líder de Proyecto, responsables de Etapas y participación/reminders futuros de
Activities. `REASSIGN` exige cuenta y membership `ACTIVE` del mismo Workspace;
`DELETE` y `DELETE_ALL` solo afectan datos futuros elegibles. Cualquier fallo
revierte el batch y no reescribe historia, organizer ni autoría pasada.

## Hard delete

`can_delete` es una proyección informativa server-side, nunca autoridad del
cliente. El servicio bloquea nuevamente el Workspace y recalcula blockers en
la transacción. Un Shared realmente nunca usado puede eliminarse aunque tenga
la membership estructural del owner; cualquier dato funcional, historia,
miembro significativo, invitación o notificación retenida lo bloquea.

## Frontend y privacidad de cache

El selector consume solo el listado ACTIVE autorizado, prefiere Personal y
rechaza IDs persistidos que dejaron de estar disponibles. Al cambiar elimina
caches scoped no compartidas y mantiene la semántica global de Inicio y
Revisión. Las keys Workspace privadas incorporan el UUID cuando existen; el
logout limpia toda la cache privada. Configuración deriva acciones de
`visible_role`, `kind`, `lifecycle` y `can_delete` entregados por servidor: esta
presentación no reemplaza la autorización backend.

Inicio, Revisión y Mi calendario permanecen globales y no adquieren filtro por
el selector. Las verticales V2 futuras deberán usar rutas y query keys scoped
por Workspace sin reutilizar las keys V1 no migradas.

## Inventario de rutas Workspace activas

```text
GET    /api/v2/workspaces
GET    /api/v2/workspaces/management
POST   /api/v2/workspaces
GET    /api/v2/workspaces/{workspace_id}/members
DELETE /api/v2/workspaces/{workspace_id}/members/{user_id}
POST   /api/v2/workspaces/{workspace_id}/leave
POST   /api/v2/workspaces/{workspace_id}/invitations
GET    /api/v2/workspaces/{workspace_id}/invitations
GET    /api/v2/workspace-invitations
POST   /api/v2/workspace-invitations/{invitation_id}/accept
POST   /api/v2/workspace-invitations/{invitation_id}/reject
POST   /api/v2/workspace-invitations/{invitation_id}/cancel
GET    /api/v2/workspaces/{workspace_id}/lifecycle
POST   /api/v2/workspaces/{workspace_id}/transfer-ownership
POST   /api/v2/workspaces/{workspace_id}/deactivate
POST   /api/v2/workspaces/{workspace_id}/reactivate
DELETE /api/v2/workspaces/{workspace_id}
```

OpenAPI contiene 17 operaciones Workspace, sin duplicados, rutas genéricas de
lookup ni bypass administrativo. Requests y responses usan esquemas explícitos
y no exponen token digest, rol global, hashes, relaciones ORM ni campos de
autoridad internos.

## Evidencia PostgreSQL y seguridad operacional

Las pruebas PostgreSQL usan exclusivamente el guard central de bases
desechables allowlisted (`lifemanager_test`/`lifemanager_v2_test`) sobre
loopback. El guard rechaza la base compartida `lifemanager`, nombres no
allowlisted y hosts remotos antes de crear engine. El fixture crea el target,
aplica Alembic hasta la única cabeza, ejecuta invariantes/concurrencia y elimina
el target en `finally`.

El gate mantiene sesión cookie HttpOnly, Origin y CSRF para mutaciones. No hay
fallback Bearer ni autoridad inferida del frontend.

## Trabajo posterior

Cada vertical de Tablas maestras, Tareas, Pendientes, Proyectos, Actividades,
Calendario, Reportes y Notificaciones aún debe concretar permisos de acción,
queries `id + workspace_id`, FKs same-Workspace y sus propias pruebas IDOR,
concurrencia e historia. Ese trabajo no reabre la foundation Workspace ni
otorga capacidades nuevas a `GLOBAL_ADMIN`.
