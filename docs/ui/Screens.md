# Pantallas objetivo de LifeManager V1

Este inventario resume el diseño objetivo. Los campos y reglas completas están en `docs/requirements/Functional.md`.

| Área | Pantalla | Función principal |
|---|---|---|
| Inicio | Inicio | Resumen operativo compacto y actualización manual. |
| Revisión | Revisión diaria | Edición por lote de Tareas, Pendientes y Pasos que requieren atención. |
| Planificación | Tareas | Crear ocurrencias, creación masiva y borrar Programadas. |
| Planificación | Pendientes | Mantener Vigencia, Categoría, nombre y fecha planificada. |
| Planificación | Proyectos / detalle | Mantener Proyecto y estructura ponderada de Pasos. |
| Seguimiento | Tareas | Registro histórico, filtros y corrección controlada de resultados. |
| Seguimiento | Pendientes | Control completo, avance y comentario con Guardar. |
| Seguimiento | Proyectos / detalle | Resumen, comentario general y seguimiento de Pasos. |
| Reportes | Tareas | Análisis por período, Categoría y Tarea maestra. |
| Reportes | Pendientes | Análisis de avance y Cumplimiento. |
| Reportes | Proyectos | Avance ponderado y Cumplimiento de Pasos. |
| Tablas | Tareas | Tareas maestras específicas del Personal Workspace. |
| Tablas | Categorías | Categorías específicas del Personal Workspace. |
| Configuración | Perfil y zona horaria | Nombre, apellido, email y selector amigable de zona. |

## Convenciones de interacción

- Tablas/listas compactas antes que tarjetas grandes.
- Filtros mediante dropdowns y fechas.
- Paginación histórica: 25 por defecto, opciones 25/50/100.
- Lápiz para correcciones, papelera para borrado elegible y `>` para detalle de Proyecto.
- Revisión no guarda por fila: una sola acción **Guardar revisión** persiste el lote.
- En Revisión > Tareas, Completado y No realizado aparecen simultáneamente; nunca se usa dropdown.
