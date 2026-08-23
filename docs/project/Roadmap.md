# Roadmap de LifeManager V2.0.0

## Estado

El diseño funcional V2 está aprobado en `docs/requirements/Functional-V2.md` y ADR-007. El roadmap oficial V2 continúa después de cerrar esta línea base funcional. El detalle completo del baseline de ejecución todavía no está disponible dentro del repositorio, por lo que no se fabrican etapas adicionales.

Las etapas conocidas y aprobadas son:

## Estructura obligatoria

El roadmap conservará exactamente estas columnas:

| Fase | Etapa | Módulo | Estado |
|---|---|---|---|
| Phase 1 — V2 Preparation | Stage 1.1 | Technical audit of the current V1.0.0 baseline | Completado |
| Phase 1 — V2 Preparation | Stage 1.2 | Update and consolidate V2 functional documentation | Completado |
| Phase 1 — V2 Preparation | Stage 1.3 | Inventory of V1 components that are reusable, modifiable, or replaceable | Completado |
| Phase 1 — V2 Preparation | Stage 1.4 | Design of the V2 logical and physical data model | Completado |
| Phase 1 — V2 Preparation | Stage 1.5 | Constraints, relationships, indexes, data integrity and V1→V2 transition plan | Completado |
| Phase 1 — V2 Preparation | Stage 1.6 | Review and update architecture and technical decisions | Completado |

`Estado` solo puede contener:

- Completado
- Pendiente

Stages 1.4–1.6 quedan cerrados por el modelo, plan de transición, `V2-Architecture-Baseline.md` y ADR-008–012. La siguiente etapa implementará el model layer V2 y sus pruebas de metadata antes de crear la migración de reset.

## Referencia histórica

El roadmap utilizado para V1 se conserva en `docs/project/V1-Roadmap-Historical.md` y no orienta la secuencia V2.
