# ADR-007: Línea base funcional de LifeManager V2.0.0

## Estado

Aceptado.

## Fecha

2026-08-22

## Contexto

LifeManager V1.0.0 implementa un Personal Workspace individual. La evolución V2 incorpora colaboración, responsables, Calendario/Actividades, historia de seguimiento, recordatorios y requisitos de seguridad que no deben confundirse con el runtime V1.

La documentación necesita distinguir la implementación actual del objetivo aprobado sin presentar V2 como existente ni convertir documentos históricos en fuentes paralelas.

## Decisión

- `docs/requirements/Functional-V2.md` es la fuente funcional autoritativa de V2.0.0.
- `docs/requirements/Functional.md`, ADR-005, ADR-006 y `docs/database/V1-Target-Data-Model.md` describen la línea base V1 actual.
- ADR-004 y `Legacy-V1-Target-Data-Model.md` continúan como historia reemplazada, no como diseño V2.
- La línea base de release es el tag anotado `v1.0.0`, commit `fafa8844f83763c837aa423d0773cd6d5782752c`.
- V2 será multiusuario y multi-Workspace; Inicio, Revisión y Mi calendario serán vistas globales.
- Tareas, Pendientes y Etapas incorporarán Responsables según su dominio.
- V2 introduce Actividades, Mi calendario, privacidad de disponibilidad, centro de notificaciones y push limitado.
- La campana es un overlay y registra eventos relevantes de membresía, asignación, Actividades y recordatorios; no genera avisos por comentarios ni uno por ocurrencia recurrente.
- Los recordatorios navegan a Inicio, Revisión, Seguimiento de Pendientes, Seguimiento de Proyectos o el contexto de Calendario/Actividad según corresponda.
- Pendientes y Etapas conservarán historia cronológica de seguimiento.
- La Categoría de ocurrencias basadas en catálogo seguirá dinámicamente la Categoría actual de su entrada maestra.
- Seguridad será transversal y tendrá gate obligatorio antes de producción.
- El registro restringido exige anti-bot, verificación de correo y aprobación global antes de activar la cuenta; su implementación física permanece pendiente.
- El retiro de miembros preserva el pasado y permite reasignar o eliminar responsabilidades futuras sin imponer reasignación; una persona Propietaria debe transferir la propiedad antes de salir.
- Los datos V1 actuales son descartables para desarrollo, pero no se ejecutará ningún reset hasta diseñar y aprobar la transición técnica.

## Consecuencias

### Positivas

- Existe una única fuente funcional V2.
- V1 permanece documentado como implementación real.
- Los equipos pueden diseñar arquitectura, modelo físico y migración sin inferir reglas desde conversaciones.
- Se fijan terminología, alcance global/Workspace, historia y seguridad.

### Costos y riesgos

- El modelo físico y contratos V1 no satisfacen responsables, colaboración, Calendario ni historia.
- La autorización implícita del Personal Workspace deberá rediseñarse.
- El cambio es amplio y requiere etapas técnicas, migración controlada y validación de seguridad.
- Las métricas y los detalles técnicos de persistencia, permisos y seguridad permanecen deliberadamente abiertos.

## No decidido por esta ADR

- Esquema físico V2.
- Contratos API concretos.
- Estrategia de reset/migración.
- Matriz de permisos detallada.
- Proveedor o mecanismo final de push.
- Adopción obligatoria de RLS.
- Roadmap detallado: se incorporará cuando se disponga del baseline aprobado completo.
