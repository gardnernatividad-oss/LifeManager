# ADR-011: Scope API y autorización de Workspace V2

## Estado

Aceptado para implementación futura. No implementado.

## Fecha

2026-08-22

## Contexto

V2 combina páginas globales y recursos de un Workspace. Un Workspace seleccionado en frontend no puede convertirse en autoridad ni estado oculto de servidor.

## Decisión

- Recursos scoped usan `/api/v2/workspaces/{workspace_id}/...`.
- Inicio, Revisión, Mi calendario, Notifications, Account y Administration son globales y agregan únicamente scopes autorizados.
- No se usa header/body/cookie de Workspace activo para autorizar.
- Services scoped reciben `workspace_id` y lo incluyen en el lookup SQL junto al resource ID.
- Dependencies reutilizables resuelven CurrentUser, GLOBAL_ADMIN, membresía ACTIVE y owner; services aplican permisos de recurso y eligibility.
- Un miembro válido recibe 404 uniforme por recurso inexistente o perteneciente a otro Workspace. Un usuario sin membership recibe 403.
- GLOBAL_ADMIN no obtiene acceso implícito a contenido privado.
- Frontend incluye Workspace ID en rutas y query keys; el selector es UX, no control de acceso.

## Consecuencias

- URLs son bookmarkeables, deep-linkable y fáciles de probar.
- IDOR se combate en dependency, query, service y DB.
- Cambios/retirada de membership invalidan selección/caches sin depender de una sesión server-side de Workspace.

## Reemplazo

ADR-003 conserva la historia del modelo inicial. Para scope, propiedad, roles visibles y autorización V2 prevalecen ADR-008, esta ADR y Permissions.md.
