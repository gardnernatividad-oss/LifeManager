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

## Diferido

Listado/selector de Workspaces, invitaciones, aceptación, administración de
miembros, privacidad, transferencia, salida y eliminación Shared no forman parte
de Stage 3.2.
