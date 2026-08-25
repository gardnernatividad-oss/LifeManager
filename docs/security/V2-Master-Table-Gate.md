# Gate de Tablas maestras V2 — Stage 4.3

## Resultado

Stage 4.3 queda **Completado**. El gate integrado valida Categorías, Tareas y
Actividades como infraestructura maestra de un Workspace. No implementa
ocurrencias, recurrencia, planificación ni Calendario.

## Matriz autoritativa

`OK` significa acceso limitado al Workspace indicado; `401`, sesión ausente o
cuenta no utilizable; `404`, Workspace o recurso ajeno/inexistente oculto. Las
operaciones de gestión agrupan listar, crear, editar, cambiar vigencia,
reclasificar y eliminar si `can_delete` es verdadero. Los selectores aplican la
misma frontera de acceso.

| Actor / estado | Personal ACTIVE | Shared ACTIVE | Shared INACTIVE | Workspace ajeno/inexistente |
|---|---:|---:|---:|---:|
| Anónimo | 401 | 401 | 401 | 401 |
| Owner Personal ACTIVE | OK | — | — | 404 |
| Owner Shared ACTIVE | — | OK | 404 | 404 |
| Member Shared ACTIVE | — | OK | 404 | 404 |
| Membership LEFT/REMOVED | — | 404 | 404 | 404 |
| No miembro | 404 | 404 | 404 | 404 |
| Cuenta DISABLED | 401 | 401 | 401 | 401 |
| GLOBAL_ADMIN sin membership | 404 | 404 | 404 | 404 |

La matriz se aplica por igual a Categorías, catálogo de Tareas, catálogo de
Actividades, lecturas de selector, reclasificación e inclusión explícita del
valor inactivo actual. Toda membership `ACTIVE` puede administrar los tres
catálogos; no existe bypass por rol global. Un Workspace `INACTIVE` no admite
lecturas ni mutaciones operativas de catálogos.

## Ciclo, normalización y eliminación

- Los nombres se limpian con trim, colapso de espacios, NFC y `casefold`; no se
  eliminan acentos. La unicidad resultante se limita al Workspace.
- Activo/Inactivo conserva identidad e historia y puede revertirse con la
  versión vigente.
- `can_delete` es una proyección calculada por servidor. El cliente no puede
  enviarla como autoridad.
- El hard delete bloquea la fila, comprueba `lock_version`, recalcula referencias
  dentro de la transacción y conserva FK `RESTRICT` como frontera final.
- Al desaparecer la última referencia, una lectura posterior vuelve a calcular
  el registro como eliminable.

## Reclasificación histórica

La clasificación de ocurrencias basadas en `MasterTask` o `ActivityMaster` es
dinámica: se interpreta mediante la Categoría actual del maestro. No existe
snapshot de Categoría en el punto histórico. La edición muestra una advertencia
breve y no ofrece variantes “solo futuras”. Cambiar Categoría conserva la
identidad del maestro y exige Categoría activa del mismo Workspace.

## Selectores y aislamiento de caché

Los selectores de Categoría, Tarea y Actividad son infraestructura genérica,
sin lógica de fechas, recurrencia o Calendario. Por defecto devuelven solo
opciones activas. `current_id` puede incluir exactamente el valor inactivo ya
referenciado, pero nunca uno ajeno o desconocido. Las query keys contienen el
Workspace, las mutaciones invalidan listados y selectores del mismo scope, el
cambio de Workspace reinicia el estado del editor y logout limpia la caché
privada.

El gate corrigió un defecto de edición: una Tarea o Actividad cuya Categoría
actual fue desactivada puede conservarla al editar únicamente el nombre. El
formulario usa el selector común con `current_id` y solo envía `category_id`
cuando existe una reclasificación real; una nueva asignación continúa exigiendo
una Categoría activa.

## API y seguridad

Las rutas activas viven exclusivamente bajo
`/api/v2/workspaces/{workspace_id}`. Los DTO son estrictos, no exponen
`normalized_name`, y `can_delete` solo aparece en respuesta. UUID aleatorios o
ajenos no revelan existencia. Las mutaciones usan control optimista; conflictos
de versión, nombre, referencia o categoría no disponible producen respuestas
seguras sin escritura parcial.

## UX, responsive y accesibilidad

Las tres pantallas usan Categorías, Tareas y Actividades como nombres visibles,
con patrones coherentes de creación, búsqueda, vigencia, edición, activación,
desactivación, confirmación de borrado y estados de carga/error/vacío. En móvil,
filtros, tarjetas y formularios pasan a una columna sin depender de scroll
horizontal. Inputs tienen labels, acciones tienen nombres accesibles, los
selectores operan con teclado y los controles deshabilitados conservan el
estándar global: atenuados, sin animación hover y cursor normal.

## Desarrollo local

No existe un bootstrap manual soportado que omita registro, verificación o
aprobación. Los tests disponen de factories y `RecordingEmailDelivery`, pero no
son un seed ejecutable ni deben apuntar a la base compartida. Para inspección
manual puede reutilizarse una cuenta local ya aprobada. Si se necesita crear una
nueva, debe seguirse el flujo V2 ordinario con un provider/recorder local y una
cuenta administradora local ya provisionada de forma operacional; el repositorio
no contiene credenciales ni un helper de elevación. Diseñar un comando local
fail-closed y auditado queda como propuesta futura no bloqueante.

## Evidencia y trabajo posterior

La validación cubre contratos unitarios, autorización Workspace reutilizada,
PostgreSQL local desechable, OpenAPI, frontend, TypeScript, lint y build. El
guard central rechaza `lifemanager`, hosts remotos y targets no allowlisted.
Phase 5 integrará estos selectores en ocurrencias de Tareas; Phase 8 hará lo
propio con Actividades. Ninguna ocurrencia de dominio se crea en Phase 4.
