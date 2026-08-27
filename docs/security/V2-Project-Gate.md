# Gate de seguridad V2 — Proyectos y Etapas

## Estado

Stage 7.4 cierra Phase 7. El gate valida los contratos implementados en Stages
7.1–7.3 sin ampliar el dominio ni el esquema físico.

## Matriz de autoridad

| Actor | Project | Etapa, seguimiento e historial |
|---|---|---|
| Miembro `ACTIVE` de Workspace `ACTIVE` | Crear, listar, consultar, editar y cambiar Vigencia, Categoría o Líder | Listar, crear, consultar, editar, cambiar Responsable/peso, registrar seguimiento y leer historial según lifecycle |
| Owner, Líder o Responsable que además es miembro `ACTIVE` | Misma autoridad, sin privilegio adicional | Misma autoridad, sin privilegio adicional |
| Anónimo, `LEFT`, `REMOVED`, no miembro o cuenta `DISABLED` | Sin acceso | Sin acceso |
| `GLOBAL_ADMIN` sin membership | Sin bypass | Sin bypass |

Cada acceso valida Workspace; una Etapa añade Project + Etapa y su historial
mantiene el mismo scope. Las referencias de Categoría, Líder y Responsable
deben pertenecer al Workspace y estar activas cuando se asignan.

## Integridad y concurrencia

- Project y Etapa usan `lock_version`; las mutaciones bloquean Project antes de
  Etapa.
- Los pesos permiten construcción progresiva, nunca superan 100 y solo una suma
  exacta de 100 habilita las proyecciones globales definitivas.
- Seguimiento crea un único `ProjectStageHistory` append-only dentro de la misma
  transacción. Actor, timestamp y tipo son server-side.
- Project inactivo y Etapa finalizada rechazan mutaciones operativas de Etapa.
- Estado, Avance global, finalización, Cumplimiento y Detalle son derivados.

## Superficie y privacidad

Las rutas de Etapa son exclusivamente jerárquicas bajo
`/api/v2/workspaces/{workspace_id}/projects/{project_id}/stages/{stage_id}`.
No existe lookup global, escritura directa de historial, bypass por rol visible
ni campos derivados/client-controlled en DTOs de escritura. Las query keys de
detalle e historial incluyen Workspace, Project y Etapa; cambio de Workspace y
logout eliminan estado privado de UI/cache.

## Evidencia

El gate incluye pruebas de rutas, servicios, DTOs, OpenAPI, PostgreSQL
desechable, carreras optimistas, IDOR jerárquico, mass assignment, lifecycle,
comentarios/history, navegación responsive, aislamiento de cache y build PWA.
No se contactó `lifemanager`, remoto ni producción.
