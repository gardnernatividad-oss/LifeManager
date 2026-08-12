# Roadmap de LifeManager V1

## Objetivo

Evolucionar de la implementación heredada al diseño funcional aprobado del Personal Workspace sin perder datos ni debilitar el aislamiento.

## Estado

La infraestructura, autenticación, modelos base, APIs y frontend PWA existen. La siguiente fase no consiste en añadir módulos aislados, sino en alinear dominio, datos y experiencia con ADR-005.

## Secuencia recomendada

1. **Auditoría y transición de datos**
   - inventariar datos existentes;
   - diseñar Tarea maestra, nueva Tarea, Pendiente, Proyecto/Paso y timestamps de revisión;
   - usar el modelo físico aprobado en `docs/database/V1-Target-Data-Model.md` y ADR-006 como base de la auditoría;
   - definir backfills y compatibilidad;
   - crear migraciones nuevas sin editar historial.
2. **Personal Workspace y registro**
   - creación transaccional completa;
   - ocultar selector/flujos colaborativos en V1;
   - perfil y selector de zona horaria.
3. **Tablas**
   - Categorías y Tareas maestras;
   - inmutabilidad después del primer uso.
4. **Planificación**
   - ocurrencias por fecha;
   - creación masiva sin serie persistente;
   - selección múltiple y borrado solo Programadas;
   - Pendientes y Proyectos/Pasos.
5. **Revisión por lote**
   - Tareas, Pendientes y Pasos relevantes;
   - Guardar final con atomicidad/error claro;
   - Última revisión.
6. **Seguimiento**
   - registros completos paginados;
   - correcciones permitidas;
   - progreso, cumplimiento y timestamps.
7. **Inicio y Reportes**
   - Inicio operativo;
   - agregaciones correctas por cada dominio;
   - reportes visuales sin mezclar edición histórica.
8. **Retiro de compatibilidad heredada**
   - retirar TaskSeries, Daily Form/Workflow, Reminder Engine y settings no V1 cuando los datos estén migrados;
   - eliminar rutas/UI obsoletas solo después de validar reemplazos.

## Criterios de finalización V1

- La implementación coincide con `docs/requirements/Functional.md`.
- Migraciones y backfills son reversibles o tienen rollback documentado.
- Pruebas cubren reglas, aislamiento, transiciones y batch save.
- UI compacta y responsive validada.
- No quedan rutas públicas que presenten conceptos explícitamente fuera de V1.

## Futuro V2

Family Workspace, colaboración, Calendario/Actividades, notificaciones/recordatorios y administración restringida podrán construirse sobre la arquitectura conservada, pero no condicionan la entrega V1.
