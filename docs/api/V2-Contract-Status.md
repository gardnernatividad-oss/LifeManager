# Estado de contratos API de LifeManager V2.0.0

## Estado

Arquitectura de contratos aprobada; endpoints y payloads verticales todavía no implementados.

Las rutas y payloads actuales pertenecen a V1.0.0. `Functional-V2.md` define comportamiento, pero no autoriza nombres de endpoints, schemas, versionado, compatibilidad ni estrategia de corte.

Convenciones aprobadas:

- prefijo nuevo `/api/v2` para contratos V2;
- recursos scoped bajo `/api/v2/workspaces/{workspace_id}/...`;
- Inicio, Revisión, Mi calendario, Notifications, Account y Administration son globales;
- no existe Workspace activo oculto en headers, body, cookie o sesión;
- lookup scoped por `workspace_id + resource_id`, con 404 neutral cross-Workspace;
- cookie de sesión HttpOnly y CSRF para operaciones unsafe;
- DTOs separados, `extra='forbid'`, respuesta mínima y paginación común;
- error envelope con `code` estable y mensaje seguro;
- `lock_version` esperado para mutaciones concurrentes y 409 en conflicto;
- reemplazo coordinado, no reutilización implícita, de contratos V1.

Los endpoints/payloads concretos se aprueban por vertical. Las reglas completas están en [`V2-Architecture-Baseline.md`](../architecture/V2-Architecture-Baseline.md), ADR-009, ADR-010 y ADR-011.

No deben reutilizarse clientes frontend heredados ni rutas V1 como especificación V2 sin una decisión explícita.
