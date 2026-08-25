# Workspaces V2

## Stage 3.6: listado, selector y gestión

Esta sección sustituye cualquier nota posterior que aún describa listado,
selector o reactivación como diferidos.

```text
GET  /api/v2/workspaces
GET  /api/v2/workspaces/management
POST /api/v2/workspaces/{workspace_id}/reactivate
```

El listado operacional devuelve solamente Workspaces `ACTIVE` con membership
`ACTIVE`: Personal primero y luego Shared por nombre e UUID. El listado de
gestión añade Shared `INACTIVE` únicamente para su Propietario. La proyección
expone rol visible y elegibilidad de eliminación derivados en servidor;
`GLOBAL_ADMIN` no amplía el resultado.

Reactivar exige al owner actual, conserva historia y memberships `ACTIVE`, y
no restaura memberships `LEFT`/`REMOVED` ni invitaciones canceladas.

## Estado

Stages 3.2–3.4 implementan creación Shared, invitaciones y el lifecycle
ordinario de membresías.

```text
POST /api/v2/workspaces
```

Una cuenta autenticada y `ACTIVE` puede crear un Workspace Compartido. La
operación está protegida por la sesión cookie, Origin y CSRF V2 existentes.

## Request

```json
{
  "name": "Familia"
}
```

El DTO es estricto y solo acepta `name`. El nombre se normaliza a Unicode NFC,
elimina whitespace exterior, colapsa whitespace repetido, admite Unicode y
rechaza nombres vacíos, mayores de 150 caracteres o con controles Cc.

El cliente no puede aportar `kind`, `owner_user_id`, `user_id`, estado/rol de
membresía, rol global, IDs, versiones, timestamps ni relaciones anidadas.

## Semántica transaccional

El backend siempre fija `kind=SHARED`, deriva `owner_user_id` de la cuenta
autenticada y crea exactamente una membresía `ACTIVE` para esa misma persona.
Workspace y membresía se insertan en una transacción cuyo único commit pertenece
a la ruta. Cualquier error revierte ambos. Nombres duplicados están permitidos;
la identidad y autorización dependen del UUID.

Personal no puede crearse mediante este endpoint y continúa aprovisionándose
exclusivamente al aprobar una cuenta.

## Response 201

```json
{
  "id": "uuid",
  "name": "Familia",
  "kind": "SHARED"
}
```

La respuesta no expone owner interno, membership, campos de auditoría ni grafo
ORM. Inmediatamente después del commit, la persona creadora cumple las fronteras
`ActiveWorkspaceMembership` y `WorkspaceOwner`.

## Invitaciones Shared

- `POST /api/v2/workspaces/{workspace_id}/invitations`: owner crea una invitación para el email normalizado de una cuenta `ACTIVE` existente.
- `GET /api/v2/workspaces/{workspace_id}/invitations`: owner lista invitaciones pendientes y no vencidas del Workspace.
- `GET /api/v2/workspace-invitations`: destinatario autenticado lista sus invitaciones pendientes y no vencidas.
- `POST /api/v2/workspace-invitations/{invitation_id}/accept`: destinatario acepta y crea/reactiva membresía ordinaria.
- `POST /api/v2/workspace-invitations/{invitation_id}/reject`: destinatario rechaza.
- `POST /api/v2/workspace-invitations/{invitation_id}/cancel`: owner del Workspace Shared cancela.

Las mutaciones usan sesión cookie, CSRF y Origin. La vigencia es de 14 días. No se expone ni entrega token; el digest interno queda reservado para una posible evolución futura. Las respuestas nunca incluyen el digest, estado interno de cuenta ni grafos ORM. Invitaciones vencidas se excluyen de listados accionables; no se requiere scheduler.

## Miembros Shared

- `GET /api/v2/workspaces/{workspace_id}/members`: cualquier Miembro `ACTIVE` lista la proyección mínima de membresías del Workspace Shared.
- `DELETE /api/v2/workspaces/{workspace_id}/members/{user_id}`: el Propietario retira a un Miembro ordinario `ACTIVE`.
- `POST /api/v2/workspaces/{workspace_id}/leave`: el Miembro ordinario autenticado sale voluntariamente.

La proyección incluye `user_id`, nombre visible, email, rol derivado
`Propietario`/`Miembro`, estado y fechas de ingreso/fin. No expone rol global,
privacidad, versiones, campos de cuenta, hashes, tokens ni grafos ORM. El rol
no se persiste: se deriva comparando `owner_user_id`.

Retiro y salida bloquean primero Workspace y luego WorkspaceMember. Mutan la
misma fila `ACTIVE` a `REMOVED` o `LEFT`, fijan `ended_at` e incrementan
`lock_version`; no hacen hard delete ni borran `calendar_visibility`. El acceso
se revoca inmediatamente porque toda ruta privada exige membresía `ACTIVE`.
Una acción repetida produce conflicto y una cuenta `GLOBAL_ADMIN` carece de
bypass. Personal no admite estas rutas colaborativas. Una invitación posterior
puede reactivar la misma fila y restablece privacidad `HIDE`.

## Lifecycle avanzado Shared

```text
GET    /api/v2/workspaces/{workspace_id}/lifecycle
POST   /api/v2/workspaces/{workspace_id}/transfer-ownership
POST   /api/v2/workspaces/{workspace_id}/deactivate
DELETE /api/v2/workspaces/{workspace_id}
```

`lifecycle` devuelve estado y `can_delete` calculado server-side. Transferir
exige otro Miembro y cuenta `ACTIVE` del mismo Workspace; el owner anterior
permanece Miembro. Desactivar conserva datos y membresías, cancela invitaciones
`PENDING` y bloquea toda operación ordinaria. `DELETE` es hard delete y solo
funciona cuando no queda ningún registro funcional/histórico; la membresía
estructural del owner no bloquea por sí sola.

Los bodies opcionales de retiro/salida aceptan una resolución estricta por
Tareas, Pendientes, Proyectos y Etapas con `REASSIGN` o `DELETE`, o
`delete_all=true`. `REASSIGN` exige destino ACTIVE del mismo Workspace.
`delete_all` afecta únicamente contenido futuro elegible del miembro. La
participación futura en Activities se marca `REMOVED` y sus reminders se
desactivan; organizer e historia no se reescriben.

## Diferido

Listado/selector general de Workspaces, interfaz de administración, privacidad,
reactivación, email y notificaciones permanecen diferidos. Selector, gestión de
inactivos y eventual reactivación pertenecen a 3.6/13.3.
