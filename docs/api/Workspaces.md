# Workspaces V2

## Estado

Stage 3.2 implementa únicamente:

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

## Diferido

Listado/selector general de Workspaces, administración general de miembros,
privacidad, transferencia, salida, eliminación Shared, email y notificaciones no
forman parte de Stage 3.3.
