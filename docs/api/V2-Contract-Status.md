# Estado de contratos API de LifeManager V2.0.0

## Estado

Pendiente de diseño.

Las rutas y payloads actuales pertenecen a V1.0.0. `Functional-V2.md` define comportamiento, pero no autoriza nombres de endpoints, schemas, versionado, compatibilidad ni estrategia de corte.

Antes de implementar deberán aprobarse:

- contexto explícito de Workspace para recursos dependientes;
- consultas globales seguras para Inicio, Revisión y Mi calendario;
- autorización por rol y membership;
- asignaciones y responsables;
- Activities/Calendar, participantes y privacidad;
- historia y concurrencia de Pendientes/Etapas;
- registro restringido, administración y recuperación de cuenta;
- notificaciones, preferencias y deep links;
- compatibilidad o reemplazo coordinado de contratos V1.

No deben reutilizarse clientes frontend heredados ni rutas V1 como especificación V2 sin una decisión explícita.
