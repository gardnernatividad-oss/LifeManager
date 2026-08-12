# ADR-005: Diseño funcional V1 del Personal Workspace

## Estado

Aceptado.

## Fecha

2026-08-11

## Contexto

La implementación y documentación anteriores evolucionaron incrementalmente y mezclaron conceptos que ya no corresponden al producto V1 final: colaboración multi-workspace, series recurrentes persistentes, Tareas asociadas a Proyectos, Daily Form como revisión, estado Cancelled y Configuración operativa extensa.

Antes del refactor se requiere una fuente estable que distinga el objetivo V1 de la implementación heredada.

## Decisión

LifeManager V1 será exclusivamente personal. Cada registro crea un único Workspace `Personal`, propiedad del usuario. La arquitectura backend multi-workspace puede mantenerse como preparación para V2, pero V1 no expone selector, colaboración, invitaciones ni workspaces adicionales.

La navegación será Inicio, Revisión, Planificación, Seguimiento, Reportes, Tablas y Configuración, con los submódulos establecidos en `docs/requirements/Functional.md`.

### Dominio de Tareas

- Una Tarea maestra estandariza nombre y Categoría.
- Una Tarea es una ocurrencia fechada de una Tarea maestra.
- La “recurrencia” es creación masiva inmediata; no se persiste una regla ni existe sincronización/materialización posterior.
- Estados: Programada, Pendiente, Completada y No Realizada.
- No existe Cancelada.
- No hay hora, descripción, prioridad, proyecto ni duración.
- Solo una Programada puede editarse/eliminarse desde Planificación.
- Un terminal puede corregirse únicamente al otro terminal.

### Pendientes y Proyectos

Un Pendiente es un asunto independiente con avance. Un Proyecto es independiente de Tareas normales y se compone de Pasos ponderados. Estado, fecha de cumplimiento, Cumplimiento y Detalle son derivados según las reglas funcionales.

### Datos maestros

Categorías y Tareas maestras pertenecen al Personal Workspace. Antes del primer uso pueden modificarse/eliminarse; después quedan estructuralmente inmutables.

### Revisión

Revisión presenta los elementos vencidos o del día que requieren atención y persiste todos los cambios mediante un Guardar final con semántica atómica o error inequívoco.

### Inicio, Reportes y Configuración

Inicio es operativo y compacto, sin analítica ni atajos. Reportes realiza análisis separado de Tareas, Pendientes y Proyectos. Configuración V1 solo expone perfil y selector amigable de zona horaria; la semana es lunes–domingo.

## Consecuencias

- El modelo actual de Task/TaskSeries y sus APIs requieren refactor y migración segura.
- Daily Form, Reminder Engine y Workspace Settings pueden permanecer temporalmente en código, pero no forman parte del producto V1 objetivo.
- Los modelos objetivo anteriores no deben usarse como especificación de implementación nueva.
- El historial de ADR se conserva, marcado como reemplazado.
- La arquitectura debe mantener aislamiento por Workspace aunque la interfaz V1 sea personal.

## Decisiones reemplazadas

Este ADR reemplaza ADR-004 para el alcance funcional V1 y limita ADR-003: el modelo multi-workspace sigue siendo una base técnica futura, pero sus flujos colaborativos no se exponen en V1.

## Fuente detallada

`docs/requirements/Functional.md` contiene las reglas completas y es la especificación funcional autoritativa.

El modelo físico fue aprobado posteriormente mediante ADR-006 y se documenta en `docs/database/V1-Target-Data-Model.md`. El archivo `docs/database/Legacy-V1-Target-Data-Model.md` es únicamente histórico y no debe orientar migraciones nuevas.
