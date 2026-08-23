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

ADR-008 define estas garantías de datos, todavía no implementadas:

- `workspaces.owner_user_id` es la única autoridad física de propiedad; el rol visible se deriva de esa columna.
- `workspace_members` conserva una fila por Workspace+User y usa lifecycle ACTIVE/LEFT/REMOVED en vez de borrar historia.
- Propietario y Miembro son los únicos roles visibles; `GLOBAL_ADMIN` vive exclusivamente en User como rol de plataforma.
- un trigger de restricción diferible exige que el propietario tenga membresía ACTIVE al commit;
- recursos asignables referencian `(workspace_id, user_id)` contra WorkspaceMember, evitando responsables, Líderes, Organizadores o Participantes de otro Workspace;
- los services validan además que la membresía esté ACTIVE bajo el locking apropiado;
- actores históricos usan User/membresía preservados y no pierden atribución cuando termina la membresía;
- una transferencia bloquea Workspace y membresías implicadas antes de cambiar propietario;
- la privacidad de calendario se almacena en la membresía y autoriza la vista consolidada de la persona frente a ese Workspace.

## Pendiente de diseño

La matriz completa de operaciones permitidas a Propietario/Miembro y los flujos API concretos siguen pendientes. Las invariantes anteriores son requisitos mínimos y no conceden permisos por omisión.
