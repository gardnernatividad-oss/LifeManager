# Autorización y roles de LifeManager

## Frontera de listado y gestión de Workspace

El listado operacional exige cuenta, Workspace y membership `ACTIVE`. El
listado de gestión puede incluir un Shared `INACTIVE` solo para su owner
persistido. `visible_role`, `can_manage` y `can_delete` se derivan en servidor.
El selector es estado cliente no autoritativo. Reactivar no revive memberships
`LEFT`/`REMOVED`, y `GLOBAL_ADMIN` no produce bypass.

## V1 actual

El runtime V1 deriva un único Personal Workspace cuya membresía es `OWNER`. Los enums técnicos también contienen `ADMIN`, `MEMBER` y `VIEWER`, pero no tienen flujos colaborativos activos.

## Objetivo V2 aprobado

- El rol global de plataforma es independiente del rol de Workspace.
- Inicialmente existe una sola persona administradora global.
- Cada usuario conserva un Personal Workspace y puede integrar Workspaces compartidos.
- La interfaz usa Propietario y Miembro; no expone enums internos.
- Los recursos se aíslan por Workspace y la autorización se aplica en servidor.
- Inicio, Revisión y Mi calendario agregan únicamente datos que el usuario puede consultar.
- Inicio exige Workspace y membership ACTIVE para todas sus proyecciones. Solo
  incluye recursos asignados al usuario y Actividades donde conserva
  participación visible; `GLOBAL_ADMIN` sin membership no obtiene acceso.
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
- Toda membresía `ACTIVE` puede consultar y administrar los catálogos del Workspace en Stage 4.1. El `workspace_id` de la ruta es la frontera de autorización; `GLOBAL_ADMIN` no tiene bypass. La eliminación física no se expone y el ocultamiento operativo usa Activo/Inactivo.
- Desde Stage 4.2, esa misma membresía puede solicitar hard delete, pero el servidor lo permite únicamente después de bloquear la fila, comprobar `lock_version` y verificar que no exista ninguna referencia retenida. Un registro referenciado devuelve conflicto y conserva la alternativa Activo/Inactivo.
- Stage 4.3 confirma esta matriz para Categorías, Tareas, Actividades y sus selectores: Personal owner, Shared owner y Shared member con membership `ACTIVE` están permitidos; LEFT/REMOVED, no miembro, cuenta DISABLED, Workspace `INACTIVE` y `GLOBAL_ADMIN` sin membership están denegados. Ver `docs/security/V2-Master-Table-Gate.md`.
- Stage 5.1 aplica la misma frontera a las ocurrencias de Tarea. Toda membresía `ACTIVE` puede crear una ocurrencia independiente y editarla o eliminarla solo mientras esté no resuelta y su fecha sea futura. Una Tarea de hoy o vencida es Pendiente, no admite edición ni reprogramación y solo el Responsable actual puede registrar `COMPLETED` o `NOT_COMPLETED`; ser Propietario no concede privilegio especial para resolver. Una Tarea resuelta es inmutable y `GLOBAL_ADMIN` continúa sin bypass.
- Stage 5.2 conserva esa autoridad para la creación recurrente: cualquier membresía `ACTIVE` de un Workspace `ACTIVE` puede crear un lote finito y asignarlo a sí misma o a otro miembro `ACTIVE` del mismo Workspace. En Personal, el Responsable se deriva del propietario. Ni IDs externos ni `GLOBAL_ADMIN` sin membresía permiten bypass.
- Stage 5.3 permite a cualquier membresía `ACTIVE` editar o eliminar una ocurrencia futura no resuelta. En generadas, `THIS` afecta solo la seleccionada y `THIS_AND_FUTURE` solo la seleccionada y posteriores futuras no resueltas del mismo batch. MasterTask y Responsable destino deben permanecer `ACTIVE` y scoped al Workspace. Pasado, hoy y resultados terminales quedan fuera del alcance bajo lock; resolver continúa reservado al Responsable.
- Stage 5.4 confirma la matriz completa: owner Personal, owner Shared y member Shared con cuenta, Workspace y membership `ACTIVE` comparten autoridad de planificación; el Responsable actual es la única autoridad de resolución. LEFT, REMOVED, no miembro, cuenta `DISABLED`, Workspace `INACTIVE` y `GLOBAL_ADMIN` sin membership no obtienen acceso. Ver `docs/security/V2-Task-Gate.md`.
- un trigger de restricción diferible exige que el propietario tenga membresía ACTIVE al commit;
- recursos asignables referencian `(workspace_id, user_id)` contra WorkspaceMember, evitando responsables, Líderes, Organizadores o Participantes de otro Workspace;
- los services validan además que la membresía esté ACTIVE bajo el locking apropiado;
- actores históricos usan User/membresía preservados y no pierden atribución cuando termina la membresía;
- una transferencia bloquea Workspace y membresías implicadas antes de cambiar propietario;
- la privacidad de calendario se almacena en la membresía y autoriza la vista consolidada de la persona frente a ese Workspace.

- Stage 6.2 mantiene la misma frontera para detalle, historial y comentarios:
  cualquier membership `ACTIVE` del mismo Workspace `ACTIVE` puede operar
  según las capacidades server-side. Owner no obtiene privilegio especial y
  `GLOBAL_ADMIN` sin membership no tiene bypass. Historial y Pending se
  resuelven siempre por `workspace_id + pending_item_id`.
- Stage 6.4 cierra la matriz de Pendientes: owner Personal, owner Shared,
  member Shared, Responsable y miembro no Responsable pueden operar si cuenta,
  Workspace y membership están `ACTIVE`, siempre sujetos al lifecycle y
  `lock_version`. LEFT, REMOVED, no miembro, cuenta `DISABLED`, Workspace
  `INACTIVE` y `GLOBAL_ADMIN` sin membership no acceden. Owner no obtiene
  privilegio especial. Ver `docs/security/V2-Pending-Gate.md`.

- Stage 7.1 autoriza crear, listar, consultar, editar, cambiar Categoría o
  Líder y activar/desactivar Proyectos a cualquier membership `ACTIVE` del
  mismo Workspace `ACTIVE`. Líder expresa responsabilidad funcional, no una
  jerarquía de permisos; owner no recibe privilegio de Project-domain y
  `GLOBAL_ADMIN` sin membership no obtiene bypass. Personal deriva el Líder al
  propietario y Shared exige una cuenta y membership `ACTIVE` del Workspace.
- Stage 7.2 aplica esa misma autoridad a Etapas. Responsable es una asignación
  funcional y no concede exclusividad; debe ser cuenta y membership `ACTIVE`
  del mismo Workspace. Toda consulta usa Workspace + Project + Etapa y toda
  mutación bloquea Project antes que Etapa. Owner, Líder y `GLOBAL_ADMIN` sin
  membership no obtienen privilegios adicionales.
- Stage 7.3 conserva esa frontera en detalle, seguimiento e historial. Project,
  Etapa e historial se resuelven siempre por la jerarquía Workspace + Project +
  Etapa; comentario y avance se guardan atómicamente bajo `lock_version`. Actor,
  timestamp y tipo de evento son exclusivamente server-side y el historial no
  admite escritura directa.
- Stage 7.4 cierra la matriz completa de Proyectos/Etapas: anónimo, `LEFT`,
  `REMOVED`, no miembro, cuenta `DISABLED`, Workspace `INACTIVE` y
  `GLOBAL_ADMIN` sin membership no acceden. Owner, Líder y Responsable no
  reciben autoridad adicional. Ver `docs/security/V2-Project-Gate.md`.
- Stage 9.3 mantiene la misma matriz para configuración, reorden y corrección
  explícita de Etapas. Todas las operaciones exigen membership `ACTIVE`, scope
  Workspace → Project → Etapa, Proyecto activo y optimistic locks vigentes;
  `GLOBAL_ADMIN` sin membership no obtiene bypass.
- Stage 8.1 autoriza crear, listar, consultar y administrar Actividades futuras
  standalone a cualquier membership `ACTIVE` del mismo Workspace `ACTIVE`.
  Organizador y owner son atribuciones sin privilegio especial; `GLOBAL_ADMIN`
  sin membership no obtiene bypass. ActivityMaster, Organizador y Participantes
  deben pertenecer activamente al mismo Workspace. `starts_at` es la frontera:
  en curso y pasadas son read-only. Un Participante solo puede retirar su propia
  participación futura y el servidor revalida lifecycle y `lock_version` bajo
  lock.
- Stage 8.5 aplica la misma autoridad a ocurrencias recurrentes. `THIS` afecta
  únicamente la ocurrencia futura elegida; `THIS_AND_FUTURE` deriva el batch en
  servidor y alcanza solo la seleccionada y posteriores futuras `SCHEDULED`.
  Organizador y owner no obtienen privilegio. Un Participante solo puede retirar
  su propia relación; Personal elimina y Shared cancela conservando historia.
  Ver `docs/security/V2-Calendar-Gate.md`.
- Stage 9.2 conserva esas fronteras para fuentes custom. Crear o propagar
  `Otra tarea`/`Otra actividad` exige Categoría activa del mismo Workspace y no
  crea maestros. La corrección terminal de Tarea corresponde únicamente al
  Responsable dentro de una membership y Workspace activos, usa
  `lock_version` y no concede bypass a owner ni `GLOBAL_ADMIN`.

## Arquitectura de enforcement V2

- `CurrentUser` autentica y exige cuenta ACTIVE; `GlobalAdmin`, `ActiveWorkspaceMembership` y `WorkspaceOwner` son dependencies reutilizables.
- Los services siempre consultan recursos por `id + workspace_id`, aplican permisos funcionales y validan que responsables/participantes sean miembros ACTIVE.
- Las FKs compuestas preservan mismo Workspace y la base de datos es la frontera final; frontend solo adapta UX.
- Un usuario no puede distinguir mediante el API un UUID inexistente de uno perteneciente a otro Workspace: ambos producen 404 desde la frontera central.
- Una sesión ausente/inválida produce 401; una operación reservada al owner produce 403 después de resolver una membresía ACTIVE válida.
- `GLOBAL_ADMIN` protege rutas de plataforma, pero no concede acceso implícito a contenido privado ni reemplaza membership.
- `AVAILABILITY_ONLY` devuelve intervalos sin objetos/detalles de Activity; `HIDE` no devuelve datos subyacentes.
- La comparación de Stage 8.4 exige viewer y target `ACTIVE` dentro del mismo
  Shared Workspace `ACTIVE`. La preferencia del target es direccional;
  `GLOBAL_ADMIN`, owner y conocer UUIDs no conceden bypass. `SHOW_DETAILS`
  tampoco concede capacidades ni acceso al Workspace de origen.

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

La sesión V2 usa cookie HttpOnly, CSRF y validación de cuenta ACTIVE implementadas en Stage 2.8; no existe bypass de Workspace asociado al rol global.

## Invariantes Personal y Shared — Stage 3.1

| Invariante | PERSONAL | SHARED |
|---|---|---|
| Owner requerido | Sí, el usuario aprobado | Sí |
| Membresía del owner | ACTIVE obligatoria al commit | ACTIVE obligatoria al commit |
| Miembros adicionales | No | Sí, mediante flujo futuro |
| Transferencia | Prohibida | Futura, transaccional |
| Eliminación ordinaria | Prohibida | Solo flujo explícito futuro |
| Conversión de kind | Prohibida | No se ofrece conversión |
| Colaboración | No | Sí |
| Rol visible | Propietario derivado | Propietario o Miembro derivados |
| Creación | Aprobación global | Etapa posterior |

`app.services.v2_workspace` concentra la resolución Workspace+membresía ACTIVE, la autoridad de owner y las guardas de invariantes. `ActiveWorkspaceMembership` y `WorkspaceOwner` exponen esa frontera a rutas V2 posteriores. El servicio usa únicamente estado persistido, scope exacto y cuenta ACTIVE; `GLOBAL_ADMIN` no participa en la decisión.

Stage 3.2 implementa exclusivamente la creación Shared: cualquier cuenta ACTIVE puede crear, el owner y la membresía ACTIVE se derivan server-side y la ruta realiza un solo commit. Un `GLOBAL_ADMIN` actúa como cualquier otra cuenta creadora y no obtiene acceso ajeno. Invitaciones, aceptación, listado/selector, retiro de miembros y transferencia siguen diferidos; deberán reutilizar las guardas centrales y respetar el trigger diferible de owner ACTIVE.

Stage 3.3 autoriza invitaciones únicamente al propietario persistido de un Workspace `SHARED`; ser Miembro o `GLOBAL_ADMIN` no concede esa facultad. Solo la cuenta `ACTIVE` vinculada como destinataria puede aceptar o rechazar. Al aceptar se crea o reactiva una membresía ordinaria; nunca se modifica `owner_user_id` ni `global_role`. Un Workspace `PERSONAL` no admite ninguna operación de invitación.

Stage 3.4 permite a toda membresía `ACTIVE` listar la proyección mínima de miembros Shared. El retiro exige Propietario persistido y objetivo ordinario `ACTIVE`; la salida voluntaria exige que el actor sea un Miembro ordinario `ACTIVE`. Ambas operaciones bloquean en orden Workspace → WorkspaceMember, actualizan la misma fila a `REMOVED` o `LEFT`, fijan `ended_at` e incrementan la versión. La siguiente autorización falla de inmediato porque la frontera solo admite `ACTIVE`. El owner no puede salir ni ser retirado, Personal queda fuera de esta superficie y `GLOBAL_ADMIN` no obtiene bypass. Las responsabilidades futuras, transferencia y eliminación Shared se resolverán juntas en Stage 3.5.

Stage 3.5 añade lifecycle `ACTIVE`/`INACTIVE` a Workspace. Toda frontera privada
exige simultáneamente cuenta, membresía y Workspace `ACTIVE`; conservar
membresías `ACTIVE` dentro de un Workspace inactivo no concede acceso. Solo la
persona Propietaria puede transferir, desactivar o solicitar hard delete de
Shared. Transferencia y resolución de salida bloquean en orden Workspace →
WorkspaceMembers ordenadas → recursos ordenados. `GLOBAL_ADMIN` no sustituye
ninguna de estas condiciones.

Stage 3.7 valida la matriz completa owner/member/nonmember/`GLOBAL_ADMIN`,
Personal/Shared, lifecycle, IDOR, mass assignment y concurrencia. El orden
canónico también rige invitaciones: Workspace se bloquea antes que Invitation
o Membership, incluidas creación, aceptación, rechazo y cancelación. La matriz
autoritativa y evidencia están en
[`V2-Workspace-Gate.md`](../security/V2-Workspace-Gate.md). La autorización de
acciones dentro de cada dominio posterior debe reutilizar esta frontera sin
crear bypass global.
- Stage 8.3 agrega `Mi calendario` exclusivamente desde participación propia.
  Organizador, owner y `GLOBAL_ADMIN` no implican inclusión. Las futuras exigen
  participación, membership y Workspace activos; la historia legítima propia
  puede seguir visible sin conceder acceso general ni capacidades de mutación.
- Stage 9.4 mantiene esa vista global cuando no hay contexto interno y exige
  membership/Workspace `ACTIVE` al filtrar un Workspace. La comparación
  multipersona solo admite targets `ACTIVE` del mismo Shared Workspace y aplica
  su privacidad individual; `GLOBAL_ADMIN` no obtiene bypass.
- Stage 10.1 agrega Revisión global exclusivamente desde asignaciones propias en
  Workspaces con membership y lifecycle `ACTIVE`. El owner y `GLOBAL_ADMIN` no
  amplían la selección ni permiten observar asignaciones ajenas. La consulta
  es read-only y mantiene `workspace_id` como contexto, no como autoridad
  aportada por el cliente.
- Stage 10.2 conserva esa misma autoridad en los tres guardados independientes:
  solo el responsable actual, con membership y Workspace `ACTIVE`, puede mutar
  una fila elegible. Las Etapas requieren además Proyecto `ACTIVE`; identificadores
  extranjeros se ocultan y `GLOBAL_ADMIN` sin membership no obtiene bypass.
- Stage 10.3 confirma mediante PostgreSQL que una fila inválida o stale revierte
  todo su bloque, incluidos historiales y agregados, sin conceder acceso adicional.
La apariencia persistida del Workspace (color e icono) puede actualizarla un
miembro ACTIVE del Workspace ACTIVE mediante contrato estricto y
`lock_version`; no concede autoridad adicional ni permite bypass a
`GLOBAL_ADMIN` sin membership.

Stage 12.1 mantiene preferencias y suscripciones Push en scope exclusivo del
usuario autenticado. No acepta `user_id` del cliente ni concede acceso por
membership, ownership o `GLOBAL_ADMIN`. Antes de una futura entrega, el servicio
revalida cuenta y preferencia; para recordatorios de Actividades también exige
participación visible, Activity futura/programada y Workspace/membership
`ACTIVE`. Una suscripción solo puede invalidarla su propio usuario.
