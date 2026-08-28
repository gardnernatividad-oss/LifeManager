# Auditoría de paridad funcional V2 — Fases 3–8

## Estado y alcance

Esta auditoría compara el runtime, modelos, migraciones, contratos API,
frontend y pruebas de las Fases 3–8 con las decisiones funcionales más
recientes. No considera una capacidad implementada solo porque aparezca en la
documentación. Los cambios de Revisión posteriores a Stage 10.1 que estén en el
working tree son trabajo en curso y quedan fuera de la evaluación de Fases
3–8.

Resultado: **54 CONFORME, 3 DESVIACIÓN, 9 FALTANTE y 0 NO APLICA**.

## Fuentes y evidencia principal

- Producto: `docs/requirements/Functional-V2.md`, ADR-007 y documentación UI.
- Arquitectura y permisos: `docs/architecture/Permissions.md`, ADR-011 y gates
  de seguridad por dominio.
- Persistencia: `backend/app/models/v2_models.py`, enums y cadena Alembic.
- Runtime: `backend/app/services/v2_*`, `backend/app/api/v2/*`, schemas V2 y
  router principal.
- Cliente: router, páginas V2, clientes API, query keys, layout y estilos.
- Evidencia ejecutable: tests V2 unitarios, routes, frontend y PostgreSQL ya
  existentes. En esta etapa no se contactó ninguna base de datos.

## Fase 3 — Workspaces y colaboración

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Personal y Shared físicamente diferenciados | CONFORME | `Workspace.kind`, creación Personal system-only y creación Shared dedicada. |
| Protección de Personal | CONFORME | No admite transferencia, salida, desactivación ni hard delete ordinario. |
| Propietario derivado y Miembro ordinario | CONFORME | `owner_user_id` es autoridad; no se confía en un rol enviado por cliente. |
| Membresías ACTIVE/LEFT/REMOVED y reingreso | CONFORME | Una fila por Workspace+User; invitación aceptada reactiva y restablece privacidad. |
| Salida/retiro con resolución de responsabilidades | CONFORME | Locking determinista y resolución por dominio antes de terminar membership. |
| Transferencia, desactivación, reactivación y eliminación | CONFORME | Shared owner-only; hard delete únicamente vacío; lifecycle preserva datos. |
| Selector contextual y separación de vistas globales | CONFORME | Scope cliente por Workspace; Inicio, Revisión y Mi calendario no usan selector. |
| Aislamiento y ausencia de bypass GLOBAL_ADMIN | CONFORME | Dependencias server-side exigen cuenta, Workspace y membership ACTIVE. |

No se detectaron desviaciones funcionales nuevas en Fase 3. La exhaustividad
de seguridad sigue respaldada por `docs/security/V2-Workspace-Gate.md`.

## Fase 4 — Tablas maestras

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Categorías Workspace-scoped | CONFORME | Unicidad normalizada, lifecycle, locking y FK compuestas. |
| Maestros de Tareas | CONFORME | Categoría obligatoria, unicidad scoped y ciclo Activo/Inactivo. |
| Maestros de Actividades | CONFORME | Mismo patrón de catálogo y aislamiento. |
| Mutación/eliminación segura de maestros | CONFORME | Capabilities server-side, RESTRICT y locks contra primera referencia. |
| Selectores reutilizables | CONFORME | Solo activos para nuevas referencias e inclusión del valor histórico actual. |
| Reclasificación histórica dinámica | CONFORME | Tareas y Actividades de catálogo resuelven Categoría desde el master actual; reportes deben conservar ese join. |
| Soporte coherente de “Otra tarea/actividad” desde selectores | CORREGIDO EN 9.2 | Los selectores reutilizables ofrecen la opción custom sin crear maestros; nombre real y Categoría manual se conservan en cada ocurrencia. |

## Fase 5 — Tareas

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Planificación con fecha, Responsable y catálogo | CONFORME | DTO estricto, referencias scoped y Personal deriva Responsable. |
| Estados Programada/Pendiente y resultados terminales | CONFORME | Estado derivado por fecha local; resultado persistido. |
| Autoridad exclusiva del Responsable para resolver | CONFORME | `resolve_task()` revalida bajo lock; futura no se resuelve anticipadamente. |
| Corrección explícita COMPLETED ↔ NOT_COMPLETED | CORREGIDO EN 9.2 | Una acción mínima dedicada alterna únicamente resultados terminales con autorización y optimistic concurrency; nunca permite volver a Pendiente. |
| Recurrencia finita DAILY/WEEKLY/MONTHLY | CONFORME | Materialización atómica, fallback mensual, límite técnico y GenerationBatch. |
| THIS / THIS_AND_FUTURE | CONFORME | Solo futuras no resueltas; historia y batch original no se reescriben. |
| Listado, filtros, paginación y responsive | CONFORME | Query server-side, orden estable y tarjetas/filas responsive. |
| Permisos, IDOR, locking y no bypass | CONFORME | Gate de Tareas cubre owner/member/LEFT/REMOVED/nonmember/admin global. |
| “Otra tarea” puntual con nombre y Categoría manual | CORREGIDO EN 9.2 | Task admite fuente XOR catálogo/custom. La fuente custom funciona puntual o con recurrencia finita y mantiene nombre, Categoría y GenerationBatch. |

## Fase 6 — Pendientes

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Vigencia independiente del Avance | CONFORME | `is_active` y `progress` son independientes; finalizar no desactiva. |
| Responsable y fecha planificada coherentes | CONFORME | FK de membership y constraint Activo↔fecha. |
| Avance 0–100 y finalización server-side | CONFORME | Rango físico; 100 fija `completion_date` local. |
| Estado, Cumplimiento y Detalle derivados | CONFORME | No se almacenan textos derivados. |
| Historial y comentario-only | CONFORME | Evento TRACKING único por operación; orden cronológico determinista. |
| Corrección explícita de Finalizado | CONFORME | 100→0..99 limpia fecha, conserva vigencia e inserta CORRECTION. |
| Listado, filtros, detalle y mobile-first | CONFORME | Filtros combinables server-side, paginación y página interna. |
| Elegibilidad futura para Revisión | CONFORME | Responsable actual, Activo, progreso <100 y fecha planificada <= hoy. |

No se detectaron desviaciones funcionales en Fase 6.

## Fase 7 — Proyectos y Etapas

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Proyecto, Categoría, Líder y Vigencia | CONFORME | Referencias scoped, lifecycle independiente y leader history. |
| Líder sin privilegio especial | CONFORME | Toda membership ACTIVE comparte autoridad operativa; owner/creator tampoco elevan permisos. |
| Etapa con Responsable, fecha, peso y posición | CONFORME | Modelo y relaciones mantienen jerarquía Project→Stage. |
| Peso decimal hasta dos decimales | CONFORME | `Numeric(5,2)` y schema Decimal. |
| Configuración válida exige suma exacta 100.00 | CONFORME | La configuración completa se guarda atómicamente bajo lock del Proyecto y rechaza cualquier total distinto de `100.00`. |
| Orden mediante subir/bajar; posición no editable | CONFORME | `position` es interno; el comando de reorden bloquea y normaliza la secuencia visible `1..N` sin huecos. |
| Avance de Etapa con hasta dos decimales | CONFORME | Stage e history usan `NUMERIC(5,2)` y los cálculos ponderados usan `Decimal`. |
| Avance/Estado/Cumplimiento del Proyecto derivados | CONFORME | Agregación ponderada y fechas se calculan desde Etapas. |
| Proyecto inactivo bloquea seguimiento | CONFORME | `_check_project()` se ejecuta bajo lock antes de mutar Etapa. |
| Etapa 100% congelada en operación ordinaria | CONFORME | Mutación normal y capacidades la vuelven read-only. |
| Corrección explícita de Etapa finalizada | CONFORME | Planning ofrece corrección explícita `100.00 → <100.00`, limpia finalización, reabre las proyecciones y registra `CORRECTION`. |
| Historial, comentario-only y navegación jerárquica | CONFORME | History append-only y páginas Proyecto→Etapa. |
| Terminología visible “Etapa” | DESVIACIÓN | Páginas V2 principales usan Etapa, pero Inicio y Reportes activos todavía muestran “Paso/Pasos”. Se corrige con el dominio correspondiente y se verifica transversalmente en 9.5. |

## Fase 8 — Calendario y Actividades

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Activity de catálogo, Organizador y participantes opcionales | CONFORME | Referencias scoped y participantes materializados. |
| Base física de Actividad libre | CONFORME | `activity_master_id` nullable, `custom_category_id`, `title` y XOR ya existen. |
| “Otra actividad” en API y UI | CORREGIDO EN 9.2 | API y UI aceptan fuente XOR catálogo/custom para creación puntual o recurrente y conservan nombre y Categoría manual. |
| Recurrencia finita y GenerationBatch | CONFORME | DAILY/WEEKLY/MONTHLY, DST estricto y materialización atómica. |
| Identidad de ocurrencia catalogada | CONFORME | Constraint Workspace+master+organizer+starts_at y conflictos seguros. |
| Timezone IANA, huecos y ambigüedad DST | CONFORME | Conversión server-side y frontend rechazan horas inválidas/ambiguas. |
| THIS / THIS_AND_FUTURE | CONFORME | Solo ocurrencias futuras; batch e historia temporal se preservan. |
| Cancelación/eliminación y salida de participante | CONFORME | Personal elimina, Shared cancela; retiro propio solo futuro. |
| Mi calendario global | CONFORME | Agrega participación propia entre Workspaces y no usa selector general. |
| Vistas Día y Semana con detalle | CONFORME | UI cambia rango y presenta detalle temporal/contextual. |
| Vista Mes | FALTANTE | `CalendarView` y UI solo admiten DAY/WEEK. Etapa 9.4. |
| Resumen mensual multi-dominio y acceso al día | FALTANTE | No existe agregación `N actividades / N tareas / N pendientes / N etapas` ni drill-down diario asociado. Puede requerir query API, no estado duplicado. Etapa 9.4. |
| Privacidad SHOW_DETAILS/AVAILABILITY_ONLY/HIDE | CONFORME | Enforcement server-side direccional, bloques opacos y no filtración de origen. |
| Comparación colaborativa y contextos Workspace | CONFORME | Shared común, target elegible y proyecciones mínimas. |
| Agrupación/filtro “Otras actividades” y Categoría manual | CORREGIDO EN 9.2 | La proyección identifica establemente la fuente custom y los listados filtran por fuente y por Categoría manual sin convertir nombres históricos en maestros. |

## Seguridad transversal

| Requisito | Estado | Evidencia / observación |
|---|---|---|
| Autorización server-side | CONFORME | Dependencias y services revalidan autoridad; frontend no es frontera. |
| Cross-user/cross-Workspace IDOR | CONFORME | Paths y FKs compuestas se acotan por Workspace; globales derivan memberships. |
| Mass assignment | CONFORME | Schemas estrictos y campos de actor/scope derivados. |
| LEFT/REMOVED y Workspace INACTIVE | CONFORME | Frontera común exige ambos lifecycles ACTIVE. |
| GLOBAL_ADMIN sin bypass | CONFORME | Rol global no participa en autorización de dominio. |
| Capabilities server-side y concurrencia | CONFORME | Flags derivados orientan UI; services vuelven a validar bajo lock/version. |

Esta conclusión no sustituye el hardening ofensivo final de Fase 17.

## Desviaciones conocidas y hallazgos nuevos

Ya estaban explícitamente anticipados por el alcance de la auditoría: corrección
de Tarea resuelta, “Otra tarea”, “Otra actividad”, orden de Etapas, suma exacta
de pesos, precisión/corrección de Etapas y vista Mes con resumen.

Hallazgos adicionales o precisiones nuevas:

1. La base física de Actividad libre ya existe y es coherente; el faltante está
   en schemas, services, API, UI, filtros y tests, por lo que probablemente no
   necesita migración principal.
2. La UI de Tracking de Tareas ya muestra una acción “Corregir”, pero el backend
   la rechaza siempre para resultados terminales: existe una falsa capability
   visual además del faltante de dominio.
3. La documentación autoritativa actual contradice las decisiones finales al
   declarar inmutables las Tareas resueltas y Etapas finalizadas y al permitir
   una configuración persistida con pesos incompletos.
4. Inicio y Reportes V2 activos aún exponen “Pasos”, aunque Planificación y
   detalle ya usan “Etapas”.
5. `position` no se presenta como input visible, pero sigue siendo
   mass-assignable por API y no hay operación de reordenamiento semántica.

## Distribución correctiva aprobada por Roadmap

- **9.2 — Tareas y Tablas:** corrección explícita Completada ↔ No realizada,
  sin volver a Pendiente ni reescribir fecha, Responsable, master o Workspace
  históricos; “Otra tarea” y “Otra actividad” con nombre real y Categoría
  manual; agrupación/filtros como “Otras tareas”/“Otras actividades” y por su
  Categoría manual; ningún master implícito; integración con catálogos y
  reclasificación histórica dinámica para elementos basados en master.
- **9.3 — Proyectos/Etapas:** `position` interno y orden visual subir/bajar con
  numeración derivada; configuración guardable solo con pesos exactamente
  100.00%; Peso y Avance con dos decimales; Proyecto inactivo sin seguimiento
  hasta reactivación; Etapa finalizada congelada salvo acción explícita de
  corrección, con recálculo de estado, fechas, cumplimiento y agregados e
  historial de la corrección.
- **9.4 — Calendario:** Día/Semana con detalle horario y elementos diarios de
  los otros dominios; vista Mes con agregados de actividades, tareas,
  pendientes y etapas sin detalle horario y navegación al día; contexto
  interno Workspace, comparación colaborativa multipersona, privacidad
  SHOW_DETAILS/AVAILABILITY_ONLY/HIDE server-side y terminología española.
- **9.5 — Gate transversal:** regresión integral de 9.2–9.4, PostgreSQL,
  concurrencia, autorización, IDOR, responsive y terminología residual.

## Riesgos de schema y migración

| Corrección | Riesgo |
|---|---|
| Otra tarea | Alto: hacer nullable `master_task_id`, añadir nombre/categoría de ocurrencia y XOR; revisar unicidad, indexes, recurrencia, reportes y backfill. |
| Corrección de resultado Task | Medio: constraints actuales admiten ambos terminales, pero debe definirse atribución/timestamp de corrección sin falsificar historia; puede requerir audit history si 9.2 lo confirma. |
| Actividad libre | Bajo/medio: columnas y XOR existen; faltan contratos. Debe revisarse identidad/recurrencia libre y no crear masters implícitos. |
| Avance decimal de Etapa/history | Alto: alteración `SmallInteger`→`Numeric`, parity ORM/Pydantic/TypeScript, agregación y reportes. |
| Configuración/reordenamiento de Etapas | Bajo de schema, alto transaccional: comandos batch, locks deterministas y constraint de posiciones. |
| Calendario Mes | Sin schema esperado; puede requerir endpoint de agregación eficiente e índices ya existentes. |

## Conclusión

Las Fases 3, 4 y 6 conservan una base sólida. Las brechas materiales se
concentran en extensibilidad libre de Tareas/Actividades, correcciones
terminales de Tareas/Etapas, configuración/precisión de Etapas y Calendario
mensual. Ninguna etapa histórica 3–8 cambia de estado. Stage 9.1 queda
Completado como auditoría; Fase 9 permanece abierta hasta 9.5.
