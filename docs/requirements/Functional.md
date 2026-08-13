# Especificación funcional de LifeManager V1 — Personal Workspace

## 1. Autoridad y estado

Este documento es la fuente funcional autoritativa para LifeManager V1. Describe el diseño objetivo aprobado; no afirma que la implementación actual ya lo cumpla. Si una especificación anterior contradice este documento, prevalece este documento y ADR-005.

LifeManager V1 es un sistema personal de planificación, revisión, seguimiento y reportes. Opera exclusivamente dentro del Workspace `Personal` creado automáticamente para cada usuario.

## 2. Flujo del producto

| Área | Pregunta que responde |
|---|---|
| Planificación | ¿Qué pretende hacer el usuario? |
| Revisión | ¿Qué requiere atención hoy y qué resultado/avance desea registrar? |
| Seguimiento | ¿Cuál es el registro actual e histórico y qué correcciones controladas se permiten? |
| Reportes | ¿Qué resultados muestran los datos acumulados? |
| Tablas | ¿Qué datos maestros estandarizan la planificación y los reportes? |
| Configuración | ¿Qué preferencias personales útiles necesita V1? |

## 3. Navegación final

```text
LifeManager
├── Inicio
├── Revisión
├── Planificación
│   ├── Tareas
│   ├── Pendientes
│   └── Proyectos
├── Seguimiento
│   ├── Tareas
│   ├── Pendientes
│   └── Proyectos
├── Reportes
│   ├── Tareas
│   ├── Pendientes
│   └── Proyectos
├── Tablas
│   ├── Tareas
│   └── Categorías
└── Configuración
```

No existen módulos V1 separados llamados Dashboard, Tareas recurrentes o Daily Workflow. Categorías pertenece a Tablas, no a Configuración.

## 4. Identidad y Personal Workspace

El registro solicita nombre, apellido, email, contraseña y confirmación. No existe username público. El login utiliza email y contraseña.

El registro es una operación transaccional que crea User, Workspace `Personal`, membresía OWNER y valores requeridos, detecta/almacena la zona horaria y entra a LifeManager. V1 admite exactamente un Personal Workspace por usuario: no hay selector, creación adicional, invitaciones, colaboración ni administración de miembros. El backend puede conservar su arquitectura multi-workspace para V2.

Todos los datos maestros y registros están aislados por `workspace_id`. Dos usuarios con un Workspace llamado `Personal` nunca comparten Categorías, Tareas maestras, ocurrencias, Pendientes, Proyectos ni reportes.

## 5. Términos del dominio

- **Tarea maestra:** definición estandarizada de Tablas > Tareas; no tiene fecha.
- **Tarea:** ocurrencia fechada de una Tarea maestra.
- **Pendiente:** asunto independiente de mediano/largo plazo con avance porcentual; no es el estado Pendiente de una Tarea.
- **Proyecto:** objetivo independiente compuesto por Pasos de proyecto; no agrupa Tareas normales.
- **Paso de proyecto:** trabajo de texto libre que existe solo dentro de un Proyecto.
- **Actividad:** bloque con hora inicial/final reservado para Calendario V2.
- **Categoría:** clasificación maestra específica del Workspace.

## 6. Tablas maestras

### 6.1 Categorías

Una Categoría solo tiene nombre. No tiene Vigencia. Si nunca fue referenciada puede renombrarse o eliminarse. Desde su primer uso queda estructuralmente inmutable: no se renombra ni elimina. Esta regla protege los reportes históricos.

### 6.2 Tareas maestras

Campos: nombre y `category_id`. La Categoría se elige al crear la Tarea maestra y se deriva automáticamente al planificar ocurrencias.

Una Tarea maestra nunca usada permite cambiar nombre/Categoría o eliminarla. Desde la primera ocurrencia, nombre y Categoría son inmutables y no se permite eliminarla.

## 7. Tareas

### 7.1 Planificación

Planificación > Tareas crea y administra ocurrencias futuras. Campos: Tarea maestra y fecha (`DATE`). No incluye descripción, prioridad, proyecto, deadline, duración ni hora.

La creación masiva denominada informalmente “recurrencia” es solo un ayudante: recibe Tarea maestra, fecha inicial obligatoria, fecha final obligatoria y días seleccionados; calcula inmediatamente las fechas y crea Tareas independientes. No persiste una regla activa, no genera después, no materializa ni sincroniza, y no ofrece “esta y futuras”. Para cambiar el patrón se eliminan ocurrencias futuras Programadas y se ejecuta otra creación masiva.

La tabla permite selección múltiple y borrado en una acción, pero solo de Tareas Programadas.

### 7.2 Estados y transiciones

| Estado | Regla | Operaciones permitidas |
|---|---|---|
| Programada | Fecha futura | Editar fecha desde Planificación o eliminar; resultado bloqueado. |
| Pendiente | Fecha local alcanzada y sin resultado terminal | Elegir Completada o No Realizada. |
| Completada | Resultado terminal | Bloqueada; lápiz permite corregir solo a No Realizada. |
| No Realizada | Resultado terminal | Bloqueada; lápiz permite corregir solo a Completada. |

No existe Cancelada ni Reprogramada. Un resultado terminal nunca vuelve a Pendiente o Programada.

### 7.3 Revisión y Seguimiento

Revisión > Tareas muestra las Tareas de hoy y anteriores todavía Pendientes. Cada fila contiene `Fecha | Tarea | No realizado | Completado`; ambas opciones son visibles, no un dropdown. La selección solo cambia el estado visual hasta presionar **Guardar revisión**.

Seguimiento > Tareas es el registro completo paginado, no crea ni elimina. Columnas: Fecha, Tarea, Categoría, Estado y controles compactos. Filtros: Desde, Hasta, Tarea maestra, Categoría y Estado; orden inicial por fecha descendente. Pendiente permite resultado; terminales permiten la corrección limitada mediante lápiz.

## 8. Pendientes

### 8.1 Planificación

Campos: Vigencia Activo/Inactivo, Categoría, nombre libre y Fecha planificada. Activo exige fecha; Inactivo exige que la fecha sea nula. Desactivar limpia la fecha planificada y reactivar exige asignar una nueva fecha desde Planificación. Seguimiento no puede asignarla. No existe tabla maestra de Pendientes ni historial de reprogramación. Planificación es el único lugar donde se cambia la fecha.

### 8.2 Reglas derivadas

El avance es 0–100. Estado: 0 = No iniciado; 1–99 = En proceso; 100 = Finalizado. Al guardar el cambio de menos de 100 a 100, Fecha de cumplimiento toma la fecha local. Al corregir por debajo de 100 vuelve a nulo; un nuevo 100 registra la nueva fecha.

Cumplimiento y Detalle son conceptos separados:

| Momento | Cumplimiento | Ejemplos de Detalle |
|---|---|---|
| Antes de finalizar | En plazo / Atrasado | Restan 146 días / 15 días de atraso |
| Finalizado | A tiempo / Con adelanto / Con retraso | 0 días / 4 días de adelanto / 3 días de retraso |

### 8.3 Revisión y Seguimiento

Revisión muestra solo activos no finalizados con fecha de hoy o vencida. Columnas: Fecha planificada, Pendiente, Avance y Comentario; solo Avance y Comentario son editables.

Seguimiento es la tabla completa. Muestra Vigencia, Categoría, Pendiente, Avance, fechas planificada/cumplimiento, Estado, Cumplimiento, Detalle y Comentario. Solo Vigencia, Avance y Comentario son editables. **Guardar** actualiza `Última actualización`; cambios de Planificación o Revisión no cambian ese timestamp.

Vista inicial: Activos no Finalizados; vencidos primero y luego fecha más cercana. Filtros: Vigencia, Categoría, Estado, Cumplimiento y rango planificado.

## 9. Proyectos y Pasos

Un Proyecto es independiente de Tareas y Pendientes. Campos: nombre libre, Vigencia y Categoría. Su Fecha planificada se calcula como la fecha máxima de sus Pasos.

Cada Paso tiene nombre libre, Fecha planificada y Peso. Un Proyecto Activo exige al menos un Paso, todas las fechas, pesos positivos y suma exacta de 100%; no se redistribuye automáticamente. Un Proyecto Inactivo puede estar incompleto, pero debe satisfacer esas reglas antes de activarse.

En Planificación, el chevron `>` abre el detalle y una tabla editable con agregado de filas y total de peso en tiempo real.

Cada Paso tiene Avance, Fecha de cumplimiento, Estado, Cumplimiento, Detalle y un Comentario actual. Sigue las reglas de avance/fecha del Pendiente. El avance del Proyecto es `Σ (peso normalizado × avance del Paso)`. Estado: todos 0 = No iniciado; todos 100 = Finalizado; cualquier otro caso = En proceso. Finalizar no cambia automáticamente la Vigencia.

Existe un Comentario general actual del Proyecto, editable solo en la tabla general de Seguimiento, y un Comentario actual por Paso. No hay historial de comentarios V1.

Revisión agrupa por Proyecto los Pasos no finalizados con fecha de hoy o vencida y permite cambiar Avance/Comentario. Seguimiento general muestra Proyecto, Categoría, Vigencia, fecha derivada, Avance, Estado, última actualización, Comentario y `>`. El detalle muestra únicamente Avance general, última actualización con hora, Guardar y la tabla de Pasos. Guardar recalcula y actualiza el timestamp independiente de ese Proyecto.

## 10. Revisión por lote

Revisión muestra fecha local y Última revisión. Incluye Tareas, Pendientes y Pasos que requieren atención hoy. Ningún cambio se persiste individualmente: **Guardar revisión** aplica el lote y actualiza Última revisión. La implementación debe proporcionar atomicidad o un resultado de error inequívoco; nunca debe comunicar que todo se guardó si una parte falló.

## 11. Inicio

Inicio muestra “Bienvenido a LifeManager, [Nombre]”, fecha local y un resumen compacto: Tareas pendientes/vencidas, Pendientes vencidos y Pasos vencidos. Puede mostrar Última revisión y Última actualización de Pendientes. Solo tiene **Actualizar**. No contiene accesos rápidos, métricas clicables, gráficos ni análisis de cumplimiento.

## 12. Reportes

Reportes es visual/analítico y se divide en Tareas, Pendientes y Proyectos; el registro editable histórico permanece en Seguimiento. Usa dropdowns y fechas, admite Esta semana, Este mes, Últimos 30 días y cualquier rango personalizado, y restablece filtros al salir.

- **Tareas:** período, Categoría y Tarea maestra; Resueltas, Completadas, No Realizadas, Pendientes cuando sea útil y tasa `Completadas / (Completadas + No Realizadas)`. No existe Cancelada.
- **Pendientes:** Activos, Atrasados, Finalizados y Cumplimiento estándar. El análisis cuantitativo usa diferencias numéricas, nunca interpreta el texto de Detalle.
- **Proyectos:** Activos, Finalizados, avance ponderado, atrasos derivables y Cumplimiento de Pasos.

## 13. Paginación

Las tablas históricas y maestras grandes se paginan con 25 filas por defecto y selector 25/50/100.

## 14. Configuración y zona horaria

Configuración V1 contiene Perfil (nombre, apellido, email) y Preferencias (zona horaria). No expone inicio de semana, recordatorios, minutos, Daily Form, generación diaria ni hora configurable. La semana es siempre lunes–domingo.

La zona horaria determina hoy, transiciones de Tarea, fecha de Revisión y fechas de cumplimiento. Se detecta al registrar y se elige mediante selector amigable (por ejemplo, `Lima (UTC-5)`), aunque internamente se almacene IANA; nunca se solicita como texto libre.

## 15. UX

La interfaz es compacta y densa. Prefiere tablas/listas y usa espacio horizontal en desktop; móvil refluye sin perder densidad. Filtros compactos usan dropdowns y fechas, no grupos grandes de chips. Acciones usan iconos pequeños cuando corresponde (lápiz, papelera, `>`). Las acciones por lote requieren Guardar explícito.

## 16. Fuera de alcance V1

Calendario, Actividades, Workspaces adicionales/familiares, colaboración, invitaciones, asignación de miembros, push, recordatorios, Notas, Metas, Finanzas, integraciones, administración avanzada, hábitos independientes y motor de recurrencia perpetua. Una futura administración restringida podrá gestionar usuarios, Workspaces, configuración del sistema, plantillas y mantenimiento; no es parte de V1 ni equivale a las Tablas del usuario.

## 17. Estado de implementación

La aplicación existente contiene módulos y contratos anteriores (entre otros, TaskSeries persistente, Daily Form, configuración ampliada, múltiples workspaces y estado Cancelled). Son implementación heredada pendiente de refactor. Este documento especifica el objetivo; la migración técnica deberá preservar datos y mantener una secuencia segura.
