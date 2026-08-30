# Contexto de LifeManager

## Estado Stage 3.7

Stage 3.6 completa listado operacional y de gestión, reactivación Shared y el
selector contextual frontend. Personal aparece primero; Shared inactivos solo
son visibles al Propietario en Configuración. La gestión integra creación,
invitaciones, miembros, transferencia y resolución de responsabilidades.
Inicio, Revisión y Mi calendario siguen globales. Stage 3.7 cerró el gate
integral de autorización e aislamiento y corrigió el orden transaccional de
invitaciones a `Workspace → WorkspaceInvitation`. La evidencia autoritativa
está en `docs/security/V2-Workspace-Gate.md`.

## Estado del producto

LifeManager V1.0.0 es la implementación publicada y la línea base técnica. El tag anotado `v1.0.0` resuelve al commit `fafa8844f83763c837aa423d0773cd6d5782752c`.

LifeManager V2.0.0 está en preparación. Su comportamiento aprobado está documentado en `docs/requirements/Functional-V2.md` y ADR-007. La base física, recurrencia, fixtures y gate técnico de Phase 1 están implementados; las APIs y pantallas funcionales V2 todavía no lo están.

## Fuentes de autoridad

| Alcance | Fuente |
|---|---|
| Runtime y comportamiento V1 actual | Código en el tag `v1.0.0`, `docs/requirements/Functional.md`, ADR-005 y ADR-006 |
| Modelo físico V1 actual | `docs/database/V1-Target-Data-Model.md` y `docs/database/ERD.md` |
| Objetivo funcional V2 aprobado | `docs/requirements/Functional-V2.md` y ADR-007 |
| Arquitectura técnica V2 aprobada; foundation parcialmente implementada | `docs/architecture/V2-Architecture-Baseline.md` y ADR-009–012 |
| Permisos y autorización V2 | `docs/architecture/Permissions.md` y ADR-011 |
| Modelo lógico/físico V2 aprobado e implementado | `docs/database/V2-Target-Data-Model.md`, `docs/database/V2-ERD.md`, `docs/database/V2-Data-Model-Status.md` y ADR-008 |
| Transición física V2 implementada y validada solo en DB local/test desechable | `docs/database/V2-Transition-Implementation-Plan.md` |
| Contrato API transversal V2, no implementado | `docs/api/V2-Contract-Status.md`, ADR-010 y ADR-011 |
| Seguridad y requisitos no funcionales V2 | `docs/requirements/NonFunctional.md` |
| Threat model y backlog de seguridad V2 | `docs/security/V2-Threat-Model.md` |
| Auditoría de secretos, bundle, storage y configuración cloud V2 | `docs/security/V2-Secrets-and-Exposure-Audit.md` |
| Roadmap V2 | `docs/project/Roadmap.md` |
| Referencia histórica V1 | tag `v1.0.0`, `docs/requirements/Functional.md`, `docs/database/V1-Target-Data-Model.md`, `docs/database/ERD.md`, ADR-005 y ADR-006 |
| Futuro no aprobado | `docs/requirements/FutureIdeas.md`, cuando se documente expresamente como idea |

En caso de contradicción funcional prevalecen `Functional-V2.md` y ADR-007. En cada asunto técnico prevalece la fuente especializada indicada en la tabla y su ADR correspondiente. Ningún documento V2 implica que el runtime actual ya tenga esa capacidad.

## V1 actual

- PWA personal en español con autenticación Bearer JWT.
- Un Personal Workspace creado automáticamente por usuario.
- Categorías y catálogo de Tareas.
- La API V2 y la interfaz gestionan Categorías, Tareas de catálogo y Actividades de catálogo dentro del Workspace seleccionado. Los nombres técnicos `MasterTask` y `ActivityMaster` no se exponen en la interfaz.
- Planificación, Revisión, Seguimiento y Reportes para Tareas, Pendientes y Proyectos con componentes internos `ProjectStep` (Etapas en la terminología V2).
- Inicio operativo y Configuración de perfil/zona horaria.
- Backend FastAPI, SQLAlchemy 2.x, Alembic y PostgreSQL.
- Frontend React, TypeScript, Vite y TanStack Query.

V1 no expone colaboración, responsables, Calendario/Actividades, notificaciones, historia cronológica de Pendientes/Etapas ni administración global.

## V2 aprobado

- Personal Workspace y Workspaces compartidos.
- Roles globales separados de roles de Workspace.
- Responsables para Tareas, Pendientes y Etapas.
- Vistas globales Inicio, Revisión y Mi calendario.
- Actividades, Calendario consolidado y privacidad para comparación.
- Historia cronológica de Pendientes y Etapas.
- Centro de notificaciones como overlay para eventos relevantes de membresía, asignación, Actividades y recordatorios; sin avisos por comentarios.
- Registro restringido con anti-bot, verificación de correo, aprobación global y requisitos de seguridad reforzados.
- UX mobile-first con páginas internas de detalle.

## Transición

Los datos V1 existentes son de prueba/no esenciales. El reset controlado V1→V2 no se ejecutó contra producción. Durante la validación inicial de Stage 3.4, un target cacheado provocó que el reset alcanzara accidentalmente la base local compartida `lifemanager`; no contenía datos personales V2 en uso autorizado y no se intentó restaurar V1. El harness quedó corregido con target Alembic explícito y allowlist fail-closed limitada a `lifemanager_test`/`lifemanager_v2_test`. Tras publicar V2 y comenzar uso real, los resets destructivos dejan de ser aceptables y toda evolución deberá preservar datos de producción.

Phase 0 cerró cinco bloques de diseño funcional mediante Functional‑V2, ADR‑007, navegación, pantallas y sistema de diseño. Phase 1 cerró los once stages de preparación: baseline documental, modelo, estrategia de reset/transición V1→V2, los 25 modelos V2, la revisión `e4f5a6b7c8d9`, constraints PostgreSQL, recurrencia, fixtures y gate técnico. Phase 2 completó threat model y auditoría de exposición. Stages 2.4–2.7 implementaron el lifecycle de identidad, recovery y política Argon2id. Stage 2.8 implementó sesión cookie HttpOnly/CSRF y Stage 2.9 rate limiting PostgreSQL distribuido. Stage 2.10 añadió Turnstile server-side a registro, recovery y reenvío con integración mínima en el registro frontend. Stage 2.11 cerró validación/input/output y Stage 2.12 la regresión ofensiva. Stage 2.13 queda Completado: aprobó el gate técnico local, incluidos 47 tests PostgreSQL sobre una base desechable, y cerró `SEC-SECRET-001` mediante rotación/revocación de la credencial PostgreSQL local histórica. El Personal Workspace nace únicamente tras aprobación global. Siguen pendientes como requisitos operacionales las credenciales Cloudflare productivas, una `SECRET_KEY` productiva fuerte, única y backend-only, el proveedor real de email, CSP/security headers y hardening operacional.

Stage 3.1 estableció la foundation Workspace definitiva sin cambiar el esquema ni publicar rutas nuevas. La autorización privada se deriva de cuenta `ACTIVE` y membresía `ACTIVE`, nunca de `GLOBAL_ADMIN`; el rol Propietario se deriva de `owner_user_id`. Personal mantiene un único owner, no admite miembros adicionales y no puede eliminarse, transferirse ni convertirse mediante operaciones ordinarias. La colaboración Shared, sus invitaciones, membresías y transferencia se implementarán en etapas posteriores sobre esta frontera.

Stage 3.2 añadió la creación autenticada de Workspace Compartido. El cliente aporta únicamente el nombre; el backend fija `SHARED`, deriva al owner de la sesión, crea su membresía `ACTIVE` en la misma transacción y devuelve una proyección mínima. Personal continúa siendo system-only durante aprobación. Listado/selector, invitaciones, administración de miembros, transferencia y eliminación Shared siguen diferidos.

Stage 4.2 añade elegibilidad de eliminación de catálogos derivada en servidor, hard delete solo sin referencias, selectores activos reutilizables e inclusión explícita del valor inactivo actualmente referenciado.

Stage 4.3 cierra el gate integral de Tablas maestras: confirma la matriz de
autorización sin bypass `GLOBAL_ADMIN`, normalización y lifecycle de los tres
catálogos, eliminación segura, reclasificación histórica dinámica, selectores
reutilizables, aislamiento de Workspace/caché y UX responsive/accesible. No
existe snapshot histórico de Categoría ni se implementaron ocurrencias. La
evidencia está en `docs/security/V2-Master-Table-Gate.md`.

Stage 5.1 implementa la vertical V2 de Tareas puntuales: creación, listado,
detalle, edición, asignación, resolución y eliminación futura dentro del
Workspace seleccionado. Toda membresía `ACTIVE` puede crear y editar una Tarea
independiente no resuelta únicamente mientras su fecha siga siendo futura.
Una Tarea Programada no se resuelve anticipadamente; una Tarea de hoy o vencida
ya es Pendiente y solo la persona responsable actual puede resolverla.
La propiedad del Workspace no concede autoridad especial de ejecución. El
estado Programada/Pendiente se deriva de `planned_date` y la fecha local de la
cuenta; las Tareas resueltas son inmutables.

Stage 5.2 añade creación recurrente finita DAILY/WEEKLY/MONTHLY con límites
inclusivos obligatorios, lunes=0, múltiples días semanales o mensuales y
fallback 29/30/31 al último día del mes. Las fechas convergentes se deduplican
antes de persistir. Cada solicitud crea un único `GenerationBatch` inmutable y
sus ocurrencias en una transacción; cualquier conflicto existente revierte el
lote completo. Un límite técnico de 1000 ocurrencias por solicitud evita
amplificación accidental.

Stage 5.3 añade los alcances `Solo esta` y `Todas las futuras` para ocurrencias
generadas futuras no resueltas. El alcance futuro incluye la seleccionada y las
posteriores no resueltas del mismo `GenerationBatch`; preserva anteriores,
hoy/pasado y resueltas. El batch permanece como procedencia inmutable. También
se incorporaron filtros por estado derivado y origen, orden cronológico
determinista y tarjetas móviles. Cambiar el patrón y regenerar fechas sigue
diferido porque aún no existe un contrato concreto; Stage 5.4 conserva el gate
final.

Stage 5.4 cierra Phase 5 — Tareas con el gate integral documentado en
`docs/security/V2-Task-Gate.md`. La evidencia confirma autorización por
membership activa sin privilegio especial de owner ni bypass `GLOBAL_ADMIN`,
estado derivado correcto, inmutabilidad de Pendientes y resueltas, resolución
exclusiva del Responsable, aislamiento IDOR, contratos estrictos, concurrencia,
PostgreSQL desechable, caché por Workspace y UX responsive. La regeneración de
fechas al cambiar el patrón de recurrencia continúa diferida y no se describe
como implementada.

Stage 3.3 añadió el lifecycle autenticado de invitaciones Shared para cuentas `ACTIVE` existentes. Solo el propietario crea y cancela; solo el destinatario vinculado acepta o rechaza. La aceptación crea una membresía ordinaria o reactiva la fila histórica `LEFT`/`REMOVED`, reiniciando `joined_at`, limpiando `ended_at` y restableciendo `calendar_visibility=HIDE`. No se entrega token, no se envía email y no se crea notificación en esta etapa.

Stage 3.4 completó el lifecycle ordinario de membresías Shared: cualquier Miembro `ACTIVE` puede consultar la lista mínima de miembros; un Miembro ordinario puede salir y el Propietario puede retirar a otro Miembro. Propietario/Miembro son roles visibles derivados de `owner_user_id`; V2 no persiste `WorkspaceRole`, y `GLOBAL_ADMIN` permanece independiente y sin bypass. La fila no se elimina: pasa a `LEFT` o `REMOVED`, conserva historia y privacidad almacenada, fija `ended_at` e invalida inmediatamente el acceso. El Propietario no puede salir ni ser retirado y Personal no expone estas operaciones. El reingreso mediante una invitación nueva conserva la semántica de Stage 3.3. El gate corrigió además el aislamiento de bases PostgreSQL automatizadas. La transferencia, eliminación y resolución transaccional de responsabilidades futuras quedan para Stage 3.5; la interfaz visible para administrar Workspaces se mantiene en 3.6/13.3.

Stage 3.5 completó el lifecycle avanzado Shared. La propiedad se transfiere a
otro Miembro ACTIVE sin expulsar al owner anterior. Un Workspace con datos se
desactiva y conserva; uno actualmente vacío puede eliminarse físicamente tras
revalidación server-side. Cuenta, membresía y Workspace deben estar ACTIVE para
operar. Salida/retiro resuelven atómicamente responsabilidades futuras y
preservan historia. La gestión visual de activos/inactivos y una eventual
reactivación siguen en Stage 3.6.

Tras completar Stage 3.3, el roadmap V2 fue reagrupado en bloques futuros más amplios y coherentes. La reorganización no elimina, simplifica ni desplaza funcionalidad fuera de V2: conserva requisitos funcionales, técnicos, de seguridad, UX/PWA, QA y publicación. La trazabilidad detallada se mantiene en [`V2-Roadmap-Regrouping-Traceability.md`](V2-Roadmap-Regrouping-Traceability.md).

## Estado V2 de Pendientes

Stages 6.1 y 6.2 implementan planificación, ciclo, avance, cumplimiento,
detalle e historial cronológico de Pendientes. Los comentarios viven en
historia append-only; `TRACKING` representa seguimiento normal y `CORRECTION`
la reapertura explícita de un Finalizado. No existe descripción en PendingItem.
Stage 6.3 completa el listado server-side con filtros combinables por Vigencia,
Categoría, Responsable, Estado, Cumplimiento, rango de fecha y nombre. Mantiene
orden estable, paginación acotada, aislamiento de caché por Workspace y una
presentación responsive en tarjetas. Stage 6.4 confirma autorización,
aislamiento, concurrencia, seguridad de DTOs y persistencia PostgreSQL. La Fase
6 — Pendientes queda cerrada sin hallazgos HIGH abiertos.

## Estado V2 de Proyectos

Stage 7.1 implementa la gestión general V2 de Proyectos: creación, listado,
detalle, edición y lifecycle `ACTIVE`/`INACTIVE`, con Categoría y Líder válidos
del mismo Workspace. Cualquier miembro `ACTIVE` del Workspace `ACTIVE` posee la
misma autoridad operacional; Líder representa responsabilidad funcional y no
autorización, owner no recibe privilegios del dominio y `GLOBAL_ADMIN` no evita
la membresía. Personal deriva el Líder al usuario propietario. Avance, Estado,
Cumplimiento, finalización y Etapas quedan expresamente diferidos a Stage 7.2;
Stage 7.1 no ofrece eliminación de Proyectos.

Stage 7.2 incorpora Etapas workspace-scoped con Responsable activo, posición,
peso decimal, fecha planificada y avance 0–100. La suma temporal puede ser
menor a 100, pero no mayor; solo `100.00` habilita Avance ponderado, Estado,
Cumplimiento y finalización global definitivos. Etapa y Project usan optimistic
locking coordinado. Una Etapa al 100 deriva su fecha local de cumplimiento y
queda read-only. Stage 7.3 completa la navegación jerárquica Proyecto → Etapa,
el seguimiento atómico de avance con comentario opcional, comentario-only y el
historial append-only con actor y timestamp server-side. No se implementa
reapertura ni corrección de una Etapa finalizada.

Stage 7.4 cierra Phase 7: confirma la matriz uniforme de miembros activos,
aislamiento jerárquico, concurrencia, pesos/proyecciones derivadas, history
append-only, cache privada y UX responsive. La evidencia del gate se conserva
en `docs/security/V2-Project-Gate.md`.

Stage 9.3 sustituye la configuración temporal incompleta: toda configuración
guardada de Etapas suma exactamente `100.00`, el orden visible se administra
con subir/bajar y `position` permanece interno. Peso, Avance, historial y
agregación ponderada usan precisión decimal de dos posiciones. Una Etapa al
`100.00` sigue congelada para seguimiento ordinario, pero Planning dispone de
una corrección explícita que la reabre, limpia su fecha de cumplimiento y
registra `CORRECTION`; esta operación también puede reabrir el Estado derivado
del Proyecto. Los Proyectos inactivos no admiten seguimiento ni corrección.

## Estado V2 de Actividades

Stage 8.1 implementa la planificación Workspace-scoped de Actividades
standalone con catálogo activo, Organizador y Participantes activos del mismo
Workspace, intervalos zonificados, filtros y optimistic locking. Cualquier
Miembro ACTIVE del Workspace ACTIVE administra Actividades futuras; owner,
Organizador y `GLOBAL_ADMIN` no crean bypass ni jerarquías adicionales.
`starts_at` es la frontera histórica: una Actividad en curso o pasada es
completamente read-only. Un Participante puede retirarse solo de una Actividad
futura sin afectar a los demás. Stage 8.2 añade generación finita DAILY,
WEEKLY y MONTHLY como ocurrencias materiales dentro de un `GenerationBatch`.
La hora local se interpreta en la zona IANA del Workspace y cada ocurrencia
conserva su instante UTC; los huecos y ambigüedades DST se rechazan. La regla
mensual 29/30/31 cae al último día disponible y deduplica convergencias antes
de persistir. La identidad de catálogo
`workspace_id + activity_master_id + organizer_user_id + starts_at` evita
duplicados standalone/recurrentes y entre batches. Stage 8.3
implementa `Mi calendario` como consulta global por participación propia a
través de todos los Workspaces, con intersección temporal `[from,to)`, semana
desktop iniciada en lunes, día mobile y presentación en la zona IANA del
usuario. Conserva la participación histórica legítima sin restaurar acceso al
Workspace y oculta futuras retiradas o sin membership vigente.
Stage 8.4 añade comparación diaria desde un Shared Workspace común. La
preferencia direccional existente de la membresía (`HIDE` por defecto) decide
entre una proyección mínima de detalles, bloques ocupados opacos fusionados o
ningún dato. La vista de detalles queda limitada al Shared Workspace común;
Solo disponibilidad puede reflejar ocupación consolidada, siempre opaca y sin
origen, IDs ni autoridad sobre recursos del target.
Stage 8.5 cierra Calendario con scopes `THIS` y `THIS_AND_FUTURE` sobre
ocurrencias futuras materializadas. GenerationBatch no se edita; las fechas e
historia se preservan, mientras hora/duración local, catálogo, Organizador y
Participantes pueden propagarse. Personal elimina; Shared cancela conservando
la fila. El retiro propio no afecta a terceros y desactiva solo recordatorios
del actor.

Stage 10.1 implementa el motor global read-only de Revisión. La selección cruza
únicamente Workspaces y memberships `ACTIVE`, usa la fecha local de la cuenta y
devuelve bloques separados de Tareas, Pendientes y Etapas asignados al usuario
actual que requieren atención. No existe selector global de Workspace ni
bypass por `GLOBAL_ADMIN`. El guardado por bloque y su interfaz mobile-first
pertenecen a Stage 10.2.

Stage 9.1 audita la paridad funcional real de las Fases 3–8 y abre una fase de
corrección previa a Revisión. La matriz trazable está en
`docs/project/V2-Functional-Parity-Audit-Phases-3-8.md`: mantiene cerradas las
etapas históricas, concentra las correcciones en 9.2–9.4 y reserva 9.5 para el
gate integral.

Stage 9.2 implementa la fuente custom simétrica para Tareas y Actividades:
nombre real y Categoría manual, sin maestro implícito, con creación puntual o
recurrencia finita materializada. La fuente de catálogo continúa derivando
nombre y Categoría del master actual. Una Tarea terminal puede corregirse solo
entre Completada y No realizada mediante una operación dedicada; nunca retorna
a Pendiente ni reabre sus demás campos históricos.

Stage 9.4 restaura la experiencia Día/Semana/Mes. Día y Semana separan
Actividades horarias de Tareas, Pendientes y Etapas sin hora; Mes solicita una
proyección de contadores por fecha local y permite abrir Día. Mi calendario
permanece global, con contexto opcional interno de Workspace, y la comparación
diaria admite varios miembros Shared aplicando privacidad por persona.

## Principios

- Distinguir implementación actual de objetivo futuro.
- Autorizar siempre en servidor y aislar por Workspace.
- Mantener historia operativa salvo excepciones explícitas.
- Usar terminología española aprobada en la interfaz.
- Diseñar primero para móvil vertical sin degradar desktop.
- Tratar seguridad como requisito transversal, no como etapa opcional final.
Stage 9.5 cierra la paridad de Fases 3–8: Workspace persiste color e icono con
opciones seguras, Calendario deja de derivar colores del UUID y la
terminología pública queda uniformada en Etapa/Etapas. La regresión
transversal conserva Review 10.1 y deja 10.2 pendiente.
