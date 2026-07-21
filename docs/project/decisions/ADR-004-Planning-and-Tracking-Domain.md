# ADR-004: Dominio de planificación y seguimiento

## Estado

Aceptado.

## Fecha

2026-07-20

---

## Contexto

LifeManager necesita distinguir conceptos que una implementación convencional de tareas puede mezclar, pero que representan necesidades, ciclos de vida y formas de medición diferentes.

La Versión 1 tendrá cuatro conceptos principales:

1. `Task` o Tarea: una acción puntual asignada a una fecha de calendario, sin hora ni duración, evaluada mediante seguimiento diario y posiblemente recurrente.
2. `TrackedItem` o Pendiente: un asunto de mayor duración seguido durante varios días o semanas mediante porcentaje de avance y fecha planificada de finalización.
3. `Project` o Proyecto: un contenedor que agrupa Tareas relacionadas y cuyo progreso inicial se calcula a partir de ellas.
4. `Activity` o Actividad: una futura entidad de Calendario de la Versión 2, con hora de inicio y hora de fin.

Cada ocurrencia de una Tarea recurrente deberá conservar su propia fecha planificada y su propio resultado. Las Actividades no deberán mezclarse con las Tareas.

La implementación actual de Tareas fue construida como un CRUD convencional. Su modelo incluye estados y campos que no representan correctamente esta definición, por lo que deberá evolucionar de manera incremental y mediante nuevas migraciones.

---

## Decisión

LifeManager separará formalmente los dominios de Planificación, Seguimiento y Reportes, y distinguirá Tareas, Pendientes, Proyectos y Actividades como conceptos independientes.

---

## Navegación de la aplicación

La navegación aprobada será:

```text
Dashboard

Planificación
├── Tareas
├── Pendientes
└── Proyectos

Seguimiento
├── Tareas
├── Pendientes
└── Proyectos

Reportes
├── Tareas
├── Pendientes
└── Proyectos

Configuración
├── Usuario
├── Categorías
└── Preferencias
```

El Dashboard será el inicio de la aplicación y permanecerá separado de Reportes.

El Dashboard responderá principalmente:

> ¿Qué necesita atención ahora?

Reportes responderá principalmente:

> ¿Qué resultados y patrones históricos estoy obteniendo?

---

## Definición de Tarea

Una Tarea representará una acción puntual asignada exactamente a una fecha de calendario planificada.

Una Tarea:

- utilizará una fecha, nunca una hora;
- no tendrá hora límite;
- no tendrá duración;
- podrá pertenecer a una categoría;
- podrá pertenecer a un proyecto;
- podrá ser una ocurrencia de una serie recurrente;
- será evaluada mediante seguimiento diario.

El modelo persistido objetivo tendrá:

- `id`;
- `workspace_id`;
- `created_by_id`;
- `title`;
- `description`, opcional;
- `planned_date`;
- `category_id`, opcional;
- `project_id`, opcional;
- `task_series_id`, opcional;
- `resolution`, nullable;
- `resolved_at`, nullable;
- `created_at`;
- `updated_at`.

El dominio de Tareas no incluirá:

- prioridad;
- porcentaje manual de avance;
- reprogramación desde Seguimiento.

Los siguientes campos de la implementación actual no forman parte del modelo objetivo:

- `status`;
- `priority`;
- `due_at`;
- `completed_at`;
- `position`;
- `is_archived`.

Estos campos podrán permanecer temporalmente durante la migración, pero no definirán el diseño final.

---

## Estado y resolución de Tareas

Solo se persistirá una resolución terminal nullable con estos valores:

- `COMPLETED`;
- `NOT_COMPLETED`;
- `CANCELLED`.

El estado público se calculará de la siguiente manera:

1. si existe `resolution`, el estado público será esa resolución;
2. si no existe resolución y `planned_date` es posterior a la fecha local efectiva, el estado será `SCHEDULED`;
3. si no existe resolución y `planned_date` es igual o anterior a la fecha local efectiva, el estado será `PENDING`.

`SCHEDULED` y `PENDING` no se persistirán.

Esta decisión evita:

- trabajos automáticos de actualización de estado a medianoche;
- estados almacenados obsoletos;
- inconsistencias entre fecha planificada y estado persistido.

---

## Comportamiento de Seguimiento

El seguimiento diario permitirá resolver una Tarea únicamente como:

- `COMPLETED`;
- `NOT_COMPLETED`.

La cancelación ocurrirá únicamente desde Planificación.

Si una Tarea permanece sin resolver:

- continuará con estado público `PENDING`;
- aparecerá en listas diarias posteriores;
- conservará siempre su `planned_date` original.

Seguimiento no ofrecerá reprogramación.

---

## Recurrencia de Tareas

LifeManager utilizará una entidad `TaskSeries` junto con Tareas materializadas. No se utilizará el nombre `TaskTemplate`, porque la entidad representa una serie recurrente finita con fechas de inicio y fin que genera ocurrencias individuales.

La definición de recurrencia deberá soportar:

- diaria;
- días seleccionados de la semana;
- semanal;
- quincenal;
- mensual;
- anual;
- `start_date` obligatoria;
- `end_date` obligatoria.

Toda recurrencia será finita en la Versión 1. `end_date` deberá ser igual o posterior a `start_date`. No se permitirán recurrencias abiertas o infinitas.

Las ocurrencias generadas deberán permanecer dentro del rango inclusivo formado por `start_date` y `end_date`. Extender una recurrencia requerirá actualizar explícitamente `end_date`.

Cada Tarea generada será una ocurrencia independiente con:

- su propio `planned_date` inmutable;
- su propia `resolution`;
- su propio `resolved_at`.

Deberá existir una restricción de unicidad equivalente a:

```text
UNIQUE (task_series_id, planned_date)
```

La generación deberá ser idempotente.

La Versión 1 generará inmediatamente todas las ocurrencias dentro del rango finito y no requerirá un worker de fondo. Antes de insertar, el service calculará la cantidad esperada de ocurrencias y aplicará una salvaguarda técnica configurable para rechazar solicitudes operacionalmente inseguras mediante un error de validación claro.

Esta salvaguarda no constituirá una duración o cantidad máxima permanente del dominio. Deberá revisarse cuando la implementación y las pruebas de carga aporten evidencia.

La recurrencia mensual utilizará el día de `start_date` como ancla. Si ese día no existe en un mes objetivo, se utilizará el último día calendario de ese mes y se conservará el ancla original para meses posteriores. Por ejemplo, una serie iniciada el 31 de enero continuará el 28 o 29 de febrero, el 31 de marzo y el 30 de abril.

La recurrencia anual utilizará el mes y día de `start_date` como ancla. Una serie iniciada el 29 de febrero ocurrirá el 28 de febrero en años no bisiestos y volverá al 29 de febrero en años bisiestos.

Los cálculos utilizarán aritmética de fechas de calendario, no duraciones fijas expresadas en días.

### Restricciones obligatorias

La definición recurrente deberá validar como mínimo:

- presencia de `start_date` y `end_date`;
- `end_date >= start_date`;
- ninguna fecha generada anterior a `start_date`;
- ninguna fecha generada posterior a `end_date`.

La edición de ocurrencias futuras deberá conservar intactas las ocurrencias históricas. Cuando corresponda, los cambios futuros podrán cerrar una serie existente y crear una nueva definición efectiva desde una fecha determinada.

No se utilizará una única Tarea mutable para representar toda una serie.

Tampoco se utilizarán exclusivamente ocurrencias virtuales generadas de forma diferida sin persistencia, porque cada fecha necesita identidad, resultado e historial independientes.

---

## Lista diaria

La Versión 1 utilizará una entidad mínima `DailyChecklistSubmission`.

Esta entidad registrará:

- workspace;
- usuario;
- fecha de la lista;
- fecha y hora de envío;
- comentario general opcional.

Deberá existir una restricción de unicidad equivalente a:

```text
UNIQUE (workspace_id, user_id, checklist_date)
```

La propia Tarea conservará su resolución y la fecha y hora de resolución.

La Versión 1 no creará una tabla duplicada de historial `DailyChecklistItem`. Esta decisión podrá revisarse si posteriormente se requiere conservar una fotografía exacta de cada elemento mostrado o múltiples decisiones históricas sobre la misma Tarea.

---

## Pendientes

El nombre técnico provisional será `TrackedItem`.

El nombre visible para usuarios en español será Pendiente.

Un Pendiente tendrá:

- ciclo de vida activo o inactivo;
- categoría;
- título;
- descripción opcional;
- porcentaje de avance entre 0 y 100;
- fecha planificada de finalización;
- fecha real de finalización;
- historial de progreso;
- comentarios periódicos.

El estado será calculado y el usuario no lo seleccionará manualmente:

- 0 por ciento: `NOT_STARTED`;
- 1 a 99 por ciento: `IN_PROGRESS`;
- 100 por ciento: `COMPLETED`.

El desempeño respecto del calendario también será calculado, no almacenado como texto fijo. Podrá indicar:

- próximo a vencer;
- vencido;
- completado antes de tiempo;
- completado a tiempo;
- completado tarde.

Se utilizará una entidad `TrackedItemProgressUpdate` para conservar un historial inmutable de porcentajes, comentarios, usuario y fecha de cada actualización.

---

## Proyectos

Un Proyecto agrupará Tareas relacionadas.

El alcance inicial incluirá:

- nombre;
- descripción opcional;
- categoría;
- fecha de inicio opcional;
- fecha objetivo;
- ciclo de vida;
- Tareas asociadas;
- progreso calculado;
- campos de auditoría.

El progreso inicial se calculará a partir de las Tareas asociadas.

La Versión 1 no incluirá gestión avanzada de:

- portafolios;
- dependencias;
- costos;
- recursos.

---

## Categorías

Las categorías serán datos maestros persistidos en base de datos desde la Versión 1.

Podrán aplicarse a:

- Tareas;
- Pendientes;
- Proyectos.

Una categoría utilizada será desactivada en lugar de eliminarse físicamente.

La administración inicial podrá realizarse mediante un flujo mínimo dentro de Configuración. La administración completa por parte de un administrador podrá ampliarse posteriormente.

---

## Política de zona horaria

La Versión 1 estará enfocada en uso personal.

La fecha local efectiva se determinará utilizando la zona horaria IANA del usuario autenticado.

El modelo `User` ya almacena `timezone` y utiliza `America/Lima` como valor predeterminado.

No se añadirá una zona horaria al workspace en la Versión 1.

Cuando se implementen workspaces familiares compartidos en la Versión 2, se introducirá una zona horaria explícita del workspace para que todos sus miembros compartan la misma fecha operativa.

---

## Dashboard y Reportes

El Dashboard mostrará información accionable, incluyendo:

- Tareas de hoy;
- Tareas sin resolver de fechas anteriores;
- Pendientes vencidos;
- Pendientes próximos a vencer;
- Proyectos activos;
- accesos rápidos a Planificación y Seguimiento.

Reportes ofrecerá análisis histórico separado para:

- Tareas;
- Pendientes;
- Proyectos.

---

## Alternativas consideradas

### Mantener una única entidad de Tarea para todos los conceptos

Fue descartado porque mezclaría acciones puntuales, asuntos de larga duración, proyectos y actividades con hora dentro de un mismo ciclo de vida.

### Persistir todos los estados de Tarea

Fue descartado porque `SCHEDULED` y `PENDING` dependen de la fecha local efectiva y podrían quedar obsoletos.

### Representar una recurrencia mediante una única Tarea mutable

Fue descartado porque impediría conservar resultados independientes por fecha y dañaría el historial al editar la serie.

### Utilizar únicamente ocurrencias virtuales

Fue descartado porque las ocurrencias necesitan identidad persistente, resolución, cancelación e historial propios.

### Duplicar cada Tarea dentro de un historial de lista diaria

Fue descartado para la Versión 1 porque la Tarea ya conserva su fecha planificada y resolución. Un registro mínimo de envío será suficiente inicialmente.

---

## Consecuencias positivas

- Separación clara entre Tareas, Pendientes, Proyectos y Actividades.
- Modelo de Tareas basado exclusivamente en fechas de calendario.
- Resultados independientes para cada ocurrencia recurrente.
- Historial confiable para reportes.
- Ausencia de mutaciones automáticas de estado a medianoche.
- Separación explícita entre Planificación y Seguimiento.
- Estados de Pendientes derivados de datos objetivos.
- Categorías reutilizables como datos maestros.

---

## Consecuencias negativas

- La recurrencia requiere generación idempotente y administración de series.
- El CRUD actual de Tareas deberá rediseñarse.
- Los enums y campos heredados requerirán migración.
- Los reportes dependerán de conservar resultados históricos correctamente.
- La zona horaria compartida del workspace se pospone hasta la Versión 2.
- La separación de acciones de planificación y seguimiento requerirá contratos de API específicos.

---

## Riesgos

- Alterar ocurrencias históricas al editar una serie recurrente.
- Generar dos veces una ocurrencia para la misma serie y fecha.
- Generar ocurrencias fuera del rango inclusivo de la serie.
- Permitir una recurrencia sin `end_date` y convertirla accidentalmente en infinita.
- Acortar una serie sin proteger las ocurrencias históricas ya resueltas.
- Insertar una cantidad operacionalmente insegura de ocurrencias sin calcularla ni aplicar la salvaguarda técnica configurable.
- Convertir un ajuste de fin de mes o año bisiesto en una nueva ancla y desplazar fechas posteriores.
- Permitir que Seguimiento cambie `planned_date`.
- Persistir estados calculables y dejarlos obsoletos.
- Eliminar categorías utilizadas en lugar de desactivarlas.
- Perder resultados históricos durante la migración del modelo actual.
- Interpretar la fecha local con una zona horaria distinta a la del usuario autenticado.
- Mezclar Actividades de calendario con Tareas.

---

## Dirección de migración

La migración seguirá estas reglas:

1. Se preservará el historial original de migraciones.
2. Se creará una nueva migración; no se editará la migración existente de Tareas.
3. Los campos y entidades objetivo se introducirán incrementalmente.
4. Después se actualizarán modelos, schemas, services, endpoints y pruebas.
5. Los campos heredados de Tarea se eliminarán solo cuando el nuevo comportamiento haya sido validado.
6. La prioridad no se conservará en el dominio objetivo de Tareas.

---

## Reglas derivadas

1. Una Tarea tendrá exactamente un `planned_date` de tipo fecha.
2. Una Tarea no almacenará hora, duración ni prioridad.
3. `SCHEDULED` y `PENDING` serán estados calculados.
4. Solo se persistirán resoluciones terminales.
5. Seguimiento solo permitirá `COMPLETED` y `NOT_COMPLETED`.
6. La cancelación solo ocurrirá desde Planificación.
7. Seguimiento no reprogramará Tareas.
8. Las Tareas sin resolver conservarán su fecha original y aparecerán en listas posteriores.
9. Cada ocurrencia recurrente será persistida de forma independiente.
10. La generación de recurrencias será idempotente.
11. Toda serie tendrá `start_date` y `end_date` obligatorias y `end_date >= start_date`.
12. No existirán recurrencias abiertas o infinitas en la Versión 1.
13. Ninguna ocurrencia se generará fuera del rango inclusivo de su serie.
14. Extender una recurrencia requerirá modificar explícitamente `end_date`.
15. Las ocurrencias se generarán inmediatamente mediante aritmética de calendario y con una salvaguarda técnica configurable.
16. Los ajustes de fin de mes y año bisiesto no cambiarán el ancla original de recurrencia.
17. Una TaskSeries podrá generar cero o muchas Tareas; toda Tarea generada referenciará una serie y una Tarea manual no referenciará ninguna.
18. Las categorías utilizadas se desactivarán en lugar de eliminarse.
19. El estado y desempeño de Pendientes se calcularán a partir de sus datos.
20. El progreso inicial de Proyectos se calculará desde sus Tareas.
21. La fecha efectiva de la Versión 1 utilizará la zona horaria del usuario autenticado.
22. Las Actividades con horas pertenecerán al Calendario de la Versión 2.
23. Los cambios que contradigan esta decisión deberán documentarse mediante un nuevo ADR.

---

## Documentos relacionados

- `docs/architecture/Architecture.md`
- `docs/database/Database.md`
- `docs/project/Glossary.md`
- `docs/project/ProjectContext.md`
- `docs/project/Roadmap.md`
- `docs/project/decisions/ADR-001-Project-Architecture.md`
- `docs/project/decisions/ADR-002-UUID.md`
- `docs/project/decisions/ADR-003-Workspace-Model.md`

---

## Revisión futura

Esta decisión deberá revisarse si:

- se implementan workspaces familiares compartidos;
- se necesita una zona horaria operativa por workspace;
- se requieren fotografías completas de cada lista diaria;
- las reglas de recurrencia dejan de cubrir los casos del producto;
- los Proyectos necesitan dependencias, costos o administración de recursos;
- las Actividades de Calendario requieren integraciones con Tareas;
- el modelo provisional `TrackedItem` cambia de nombre técnico.
