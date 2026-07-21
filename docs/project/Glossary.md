# Glosario

## Tarea

Acción puntual asignada exactamente a una fecha de calendario, sin hora ni duración. Toda Tarea es una ocurrencia individual: puede ser manual o haber sido generada por una Serie de tareas finita, y se evalúa mediante seguimiento diario.

## Serie de tareas

Definición técnica `TaskSeries` que genera Tareas individuales dentro de un rango inclusivo finito. Siempre tiene `start_date` y `end_date` obligatorias, con `end_date` igual o posterior a `start_date`; la Versión 1 no permite recurrencias abiertas o infinitas.

## Pendiente

Nombre visible en español de la entidad técnica provisional `TrackedItem`. Representa un asunto de mayor duración seguido durante varios días o semanas mediante porcentaje de avance, fecha planificada de finalización, comentarios e historial.

## Proyecto

Contenedor que agrupa Tareas relacionadas. En la Versión 1, su progreso se calcula a partir de las Tareas asociadas.

## Actividad

Entidad futura del Calendario de la Versión 2 que utiliza hora de inicio y hora de fin. No forma parte del dominio de Tareas.

## Planificación

Área donde se crean y organizan Tareas, Pendientes y Proyectos. Incluye decisiones como fechas planificadas, recurrencia y cancelación.

## Seguimiento

Área donde se revisa y registra la ejecución de lo planificado. En Tareas permite registrar `COMPLETED` o `NOT_COMPLETED`, pero no reprogramar.

## Dashboard

Página de inicio que resume qué necesita atención ahora y ofrece accesos rápidos a Planificación y Seguimiento. Es independiente de Reportes.

## Reportes

Área de análisis histórico que muestra resultados y patrones de Tareas, Pendientes y Proyectos.
