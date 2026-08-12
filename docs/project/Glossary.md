# Glosario de LifeManager V1

## Personal Workspace

Único Workspace de usuario expuesto en V1, creado automáticamente con nombre `Personal`. Es el límite de aislamiento de todos sus datos.

## Tarea maestra

Definición estandarizada de una acción en Tablas > Tareas, con nombre y Categoría. No es una ocurrencia y no tiene fecha.

## Tarea

Ocurrencia de una Tarea maestra asignada a una fecha de calendario, sin hora. Sus estados son Programada, Pendiente, Completada y No Realizada.

## Creación masiva de Tareas

Ayudante que calcula fechas dentro de un rango finito y crea Tareas independientes. No es una serie persistente ni un motor recurrente.

## Pendiente

Asunto independiente de mediano/largo plazo, con nombre libre, fecha planificada y avance porcentual. No debe confundirse con el estado Pendiente de una Tarea.

## Proyecto

Objetivo independiente compuesto por Pasos de proyecto. No agrupa Tareas normales ni Pendientes.

## Paso de proyecto

Trabajo de texto libre que existe únicamente dentro de un Proyecto y posee fecha planificada, peso y seguimiento propio. No se denomina Tarea.

## Actividad

Bloque con hora inicial/final reservado para Calendario V2. No es una Tarea.

## Categoría

Clasificación maestra perteneciente al Personal Workspace. Una vez usada queda inmutable para proteger reportes históricos.

## Planificación

Área donde se define y mantiene lo que el usuario pretende hacer.

## Revisión

Flujo diario por lote que muestra únicamente elementos que requieren atención hoy. No reemplaza Seguimiento.

## Seguimiento

Registro completo actual e histórico que permite actualizaciones y correcciones controladas.

## Inicio

Página inicial de resumen operativo. No es un hub analítico ni contiene accesos rápidos.

## Reportes

Área visual y estadística separada para Tareas, Pendientes y Proyectos. No permite mantener el registro histórico.

## Tablas

Área de datos maestros del Personal Workspace: Tareas maestras y Categorías.

## Vigencia

Condición Activo/Inactivo de Pendientes y Proyectos. Es distinta del Estado derivado por avance.

## Cumplimiento

Clasificación estándar respecto de la fecha planificada: En plazo/Atrasado antes de finalizar y A tiempo/Con adelanto/Con retraso después.

## Detalle

Explicación cuantitativa del Cumplimiento, expresada en días. No combina estado ni se usa como texto para cálculos estadísticos.
