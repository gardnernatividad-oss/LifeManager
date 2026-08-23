# Roadmap histórico de LifeManager V1

> **HISTÓRICO.** Este documento registra el plan utilizado para completar V1.0.0. No define el roadmap V2.

## Objetivo

Evolucionar de la implementación heredada al diseño funcional aprobado del Personal Workspace, descartando los datos de desarrollo/prueba y sin debilitar el aislamiento.

## Estado

La infraestructura, autenticación, modelos base, APIs y frontend PWA existen. La siguiente fase no consiste en añadir módulos aislados, sino en alinear dominio, datos y experiencia con ADR-005.

## Secuencia recomendada

1. **Reset de esquema y modelos objetivo**
   - tratar todos los registros actuales como datos descartables de desarrollo/prueba;
   - conservar intacto el historial Alembic y añadir migraciones nuevas;
   - validar tanto `base → head` como `head legado → head objetivo`;
   - ejecutar las etapas y gates de `docs/project/V1-Transition-and-Migration-Plan.md`;
   - no introducir backfills, archivos ni APIs paralelas para datos legados.
2. **Personal Workspace, registro y zona horaria**
   - creación transaccional completa;
   - ocultar selector/flujos colaborativos en V1;
   - perfil y selector controlado de zona horaria IANA.
3. **Categorías y Tareas maestras**
   - iniciar ambas tablas vacías;
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
8. **Retiro del runtime heredado y QA**
   - backend completado: TaskSeries, Daily Form/Workflow, Reminder Engine, settings no V1, rutas Workspace públicas y auth no versionado ya no forman parte del runtime;
   - siguiente paso: reemplazar la UI obsoleta durante el corte frontend coordinado;
   - reconstruir una base vacía mediante toda la cadena Alembic y validar el producto final.

## Criterios de finalización V1

- La implementación coincide con `docs/requirements/Functional.md`.
- La cadena Alembic completa produce el esquema objetivo desde una base vacía y documenta el alcance de los downgrades destructivos.
- Pruebas cubren reglas, aislamiento, transiciones y batch save.
- UI compacta y responsive validada.
- No quedan rutas públicas que presenten conceptos explícitamente fuera de V1.

## Futuro V2

Family Workspace, colaboración, Calendario/Actividades, notificaciones/recordatorios y administración restringida podrán construirse sobre la arquitectura conservada, pero no condicionan la entrega V1.
