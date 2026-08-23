# Autorización y roles de LifeManager

## V1 actual

El runtime V1 deriva un único Personal Workspace cuya membresía es `OWNER`. Los enums técnicos también contienen `ADMIN`, `MEMBER` y `VIEWER`, pero no tienen flujos colaborativos activos.

## Objetivo V2 aprobado

- El rol global de plataforma es independiente del rol de Workspace.
- Inicialmente existe una sola persona administradora global.
- Cada usuario conserva un Personal Workspace y puede integrar Workspaces compartidos.
- La interfaz usa Propietario y Miembro; no expone enums internos.
- Los recursos se aíslan por Workspace y la autorización se aplica en servidor.
- Inicio, Revisión y Mi calendario agregan únicamente datos que el usuario puede consultar.
- Los Responsables, Líderes, Organizadores y Participantes no deben convertirse implícitamente en roles globales.
- Solo el Organizador modifica o cancela una Actividad compartida para todos.
- La privacidad de Calendario limita la información visible durante comparación.
- Al retirar un Miembro, el pasado permanece congelado; el contenido futuro puede reasignarse o eliminarse, incluso mediante `Eliminar todo`, sin exigir reasignación.
- Una persona Propietaria debe transferir la propiedad antes de abandonar el Workspace.

## Invariantes estructurales V2

ADR-008 define estas garantías de datos, implementadas en la base física V2 y pendientes de enforcement completo en services/APIs:

- `workspaces.owner_user_id` es la única autoridad física de propiedad; el rol visible se deriva de esa columna.
- `workspace_members` conserva una fila por Workspace+User y usa lifecycle ACTIVE/LEFT/REMOVED en vez de borrar historia.
- Propietario y Miembro son los únicos roles visibles; `GLOBAL_ADMIN` vive exclusivamente en User como rol de plataforma.
- un trigger de restricción diferible exige que el propietario tenga membresía ACTIVE al commit;
- recursos asignables referencian `(workspace_id, user_id)` contra WorkspaceMember, evitando responsables, Líderes, Organizadores o Participantes de otro Workspace;
- los services validan además que la membresía esté ACTIVE bajo el locking apropiado;
- actores históricos usan User/membresía preservados y no pierden atribución cuando termina la membresía;
- una transferencia bloquea Workspace y membresías implicadas antes de cambiar propietario;
- la privacidad de calendario se almacena en la membresía y autoriza la vista consolidada de la persona frente a ese Workspace.

## Arquitectura de enforcement V2

- `CurrentUser` autentica y exige cuenta ACTIVE; `GlobalAdmin`, `ActiveWorkspaceMembership` y `WorkspaceOwner` son dependencies reutilizables.
- Los services siempre consultan recursos por `id + workspace_id`, aplican permisos funcionales y validan que responsables/participantes sean miembros ACTIVE.
- Las FKs compuestas preservan mismo Workspace y la base de datos es la frontera final; frontend solo adapta UX.
- Un miembro válido no puede distinguir mediante el API un UUID inexistente de uno perteneciente a otro Workspace: ambos producen 404.
- La falta de membresía al Workspace produce 403; una sesión ausente/inválida produce 401.
- `GLOBAL_ADMIN` protege rutas de plataforma, pero no concede acceso implícito a contenido privado ni reemplaza membership.
- `AVAILABILITY_ONLY` devuelve intervalos sin objetos/detalles de Activity; `HIDE` no devuelve datos subyacentes.

La convención completa está en [`V2-Architecture-Baseline.md`](V2-Architecture-Baseline.md) y ADR-011. La matriz detallada por operación se incorporará con cada contrato vertical; ningún permiso se concede por omisión.

## Requisitos de seguridad para implementación

- El frontend, los IDs conocidos y cualquier estado de DevTools carecen de autoridad.
- Cada operación scoped exige cuenta ACTIVE, membership ACTIVE y lookup por `resource_id + workspace_id`.
- Actor, ownership, `global_role`, destinatario, timestamps e historial se derivan de contexto server-side.
- GLOBAL_ADMIN no puede consultar contenido privado sin una membership ordinaria que lo autorice.
- Las proyecciones `AVAILABILITY_ONLY` y `HIDE` se aplican antes de serializar, nunca ocultando en frontend datos ya enviados.
- La matriz de amenazas y pruebas negativas obligatorias se encuentra en [`V2-Threat-Model.md`](../security/V2-Threat-Model.md).

## Estado de implementación de identidad

Stage 2.4 valida una dependencia `GLOBAL_ADMIN` separada que exige cuenta `ACTIVE` y `users.global_role='GLOBAL_ADMIN'` persistido. No consulta ni fabrica roles desde el body y no sustituye la resolución ordinaria de `workspace_members`. Las pruebas demuestran que una persona administradora global sin membership ACTIVE no adquiere acceso ni membership en un Personal Workspace ajeno. Aprobar o rechazar exige una solicitud `PENDING_APPROVAL`; una cuenta pendiente de verificación, activa, rechazada o deshabilitada recibe un conflicto seguro.

La aprobación bloquea la cuenta objetivo y aprovisiona en una sola transacción el estado `ACTIVE`, su evento, el Personal Workspace y la membership ACTIVE del owner. El rol global no se copia al Workspace y las consultas de la cola administrativa no cargan contenido privado.

La sesión todavía reutiliza temporalmente la validación Bearer V1; cookies/CSRF y revocación pertenecen a Stage 2.8. No debe interpretarse esta compatibilidad como el contrato de sesión final.
