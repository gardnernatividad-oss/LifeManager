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

## Pendiente de diseño

La matriz completa de roles por operación y los detalles técnicos/transaccionales de invitaciones, membresías, retiro y contenido futuro se aprobarán antes de implementar. Este documento no concede permisos por omisión ni altera la política funcional ya aprobada.
