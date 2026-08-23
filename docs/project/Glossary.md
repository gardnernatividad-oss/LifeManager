# Glosario de LifeManager

## Alcance

Las definiciones indican el lenguaje visible aprobado para V2. Los nombres técnicos V1 entre paréntesis describen implementación y no deben mostrarse normalmente en la interfaz.

## Personal Workspace

Workspace creado automáticamente para cada usuario. V1 expone únicamente este Workspace; V2 añade Workspaces compartidos.

## Workspace compartido

Espacio colaborativo con miembros y permisos. Sus roles de producto se expresan como Propietario y Miembro. No debe confundirse con un rol global de plataforma.

## Propietario

Rol de producto con control del Workspace. El enum técnico V1 correspondiente puede ser `OWNER`.

## Miembro

Persona que participa en un Workspace compartido con permisos determinados por la futura matriz de autorización V2.

## Tarea de catálogo

Definición estandarizada presentada en `Tablas → Tareas`. Internamente V1 la denomina `MasterTask`, pero la interfaz no usa “Tarea maestra”. Contiene nombre, Categoría y en V2 Vigencia.

## Tarea

Ocurrencia del catálogo asignada a una fecha y, en V2, posiblemente a un Responsable. Sus estados de producto son Programada, Pendiente, Completada y No Realizada.

## Responsable

Persona a quien corresponde una Tarea, Pendiente o Etapa. No aplica a Actividad.

## Pendiente

Asunto de seguimiento prolongado con Vigencia, Categoría, Responsable, fecha planificada, Avance e historia cronológica.

## Proyecto

Objetivo con información general, Líder y una colección ponderada de Etapas.

## Líder

Persona que lidera un Proyecto. Su autoridad exacta se definirá en la matriz de permisos V2.

## Etapa

Unidad ponderada dentro de un Proyecto, con Responsable, fecha, Avance y seguimiento. El modelo interno V1 se llama `ProjectStep`; “Paso” no es terminología visible V2.

## Actividad de catálogo

Definición reutilizable presentada en `Tablas → Actividades`, con nombre, Categoría y Vigencia.

## Actividad

Bloque de tiempo de Calendario. Puede tener Organizador y Participantes, pero no Responsable.

## Organizador

Persona que crea una Actividad y puede modificarla o cancelarla para todos.

## Participante

Miembro añadido a una Actividad. La Actividad aparece automáticamente en su calendario; no existe aceptación/rechazo.

## Mi calendario

Vista global del calendario consolidado del usuario a través de todos sus Workspaces.

## Categoría

Clasificación perteneciente a un Workspace. En V2, las ocurrencias basadas en catálogo se reportan usando la Categoría actual del catálogo, incluso históricamente.

## Planificación

Área dependiente de Workspace donde se define lo que se pretende hacer.

## Revisión

Flujo global que permite guardar de manera independiente Tareas, Pendientes y Etapas asignadas que requieren acción.

## Seguimiento

Registro completo donde se mantiene Avance, Comentario e historia según el dominio.

## Inicio

Vista global y concisa del día entre Workspaces.

## Reportes

Análisis por periodo, Responsable y Categoría cuando corresponda. Sus métricas V2 se afinarán con uso real.

## Tablas

Área de catálogos por Workspace: Tareas, Actividades y Categorías.

## Vigencia

Condición Activa/Inactiva de un catálogo o entidad. Es distinta del Estado derivado por Avance.

## Avance

Porcentaje de evolución de un Pendiente o una Etapa. No aplica como progreso manual de una Tarea puntual.

## Cumplimiento

Clasificación respecto de la fecha planificada, como En plazo, Atrasado, A tiempo, Con adelanto o Con retraso.

## Detalle

Explicación cuantitativa del Cumplimiento, normalmente expresada en días.

## Recordatorio diario

Resumen matutino diario de la información pertinente del usuario.

## Revisión diaria

Recordatorio vespertino que conduce al flujo Revisión.

## Centro de notificaciones

Panel interno de campana. Es distinto de push y no es una página completa.
