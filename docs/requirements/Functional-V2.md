# Especificación funcional de LifeManager V2.0.0

## 1. Autoridad y estado

Este documento es la fuente funcional autoritativa del objetivo aprobado para LifeManager V2.0.0. No describe funcionalidad ya implementada salvo cuando lo indica expresamente. La implementación actualmente publicada corresponde a V1.0.0 y se documenta en `Functional.md`, ADR-005, ADR-006 y el modelo físico V1.

Las etiquetas de alcance utilizadas aquí son:

- **V1 actual:** comportamiento existente que sirve como línea base técnica.
- **V2 aprobado:** comportamiento que debe implementar V2.0.0.
- **Futuro / fuera de alcance:** idea no aprobada como requisito V2.

ADR-007 registra la adopción de este objetivo. El modelo físico, los contratos API y el plan de migración V2 todavía deben diseñarse; este documento no autoriza modificar migraciones históricas.

## 2. Identidad del producto y convenciones

LifeManager V2 es una aplicación multiusuario y basada en Workspaces para planificación, revisión, seguimiento, calendario y reportes.

La interfaz es Spanish-first. No hay selector de idioma en V2. Las fechas se muestran como `dd/mm/yyyy` y la semana comienza el lunes.

### 2.1 Terminología de interfaz

Se utilizarán: Inicio, Revisión, Planificación, Seguimiento, Tareas, Pendientes, Proyectos, Etapa, Actividad, Actividades, Calendario, Mi calendario, Reportes, Tablas, Configuración, Categorías, Propietario, Miembro, Líder, Responsable, Organizador y Participantes.

En la interfaz no se utilizarán `Tasks`, `Activity`, `Project Lead`, `OWNER`, `MEMBER`, `Tareas maestras`, `Paso` ni `Paso de proyecto`. Los identificadores técnicos V2 son `MasterTask`, `ActivityMaster` y `ProjectStage`; la interfaz presenta Tarea, Actividad y Etapa. `ProjectStep` y `WorkspaceRole.OWNER` pertenecen al runtime/historial V1 y no definen el target físico V2.

## 3. Workspaces y alcance de vistas

Cada usuario tiene automáticamente un Personal Workspace y puede pertenecer a Workspaces compartidos o colaborativos. Un rol global de plataforma es distinto de un rol dentro de un Workspace. Inicialmente habrá una sola persona administradora global: el propietario del producto.

La interfaz presenta roles de Workspace como **Propietario** y **Miembro**; no expone enums internos.

### 3.1 Vistas globales

Agregan información del usuario a través de los Workspaces pertinentes y no muestran el selector global de Workspace:

- Inicio;
- Revisión;
- Mi calendario.

### 3.2 Vistas dependientes de Workspace

Planificación, Seguimiento, Reportes y Tablas utilizan el Workspace seleccionado cuando el recurso pertenece a un Workspace. Mi calendario administra su contexto colaborativo mediante controles internos propios, no mediante el selector global.

La arquitectura de autorización está definida en `docs/architecture/Permissions.md`, ADR-011 y `V2-Architecture-Baseline.md`. Cada vertical concreta su matriz de acciones sin alterar la regla server-side ni el aislamiento de Workspace.

## 4. Tareas

### 4.1 Catálogo

`Tablas → Tareas` contiene el catálogo maestro. El nombre presentado al usuario es simplemente **Tareas**. Cada entrada incluye al menos nombre, Categoría, Vigencia Activa/Inactiva y acciones de edición y eliminación sujetas a uso.

Al programar una Tarea, el selector muestra solo el nombre, por ejemplo `Tarea: [ Salir a correr ▼ ]`. La Categoría se deriva de la entrada seleccionada y no se concatena al nombre.

### 4.2 Clasificación dinámica

Las ocurrencias referencian la clasificación maestra. Si cambia la Categoría de una entrada del catálogo, las ocurrencias y reportes históricos reflejan la Categoría nueva. Esta reclasificación dinámica es una excepción explícita a la inmutabilidad histórica; no elimina ni reescribe las ocurrencias.

### 4.3 Ocurrencias y responsables

Una Tarea es una ocurrencia puntual asignada a una fecha y puede tener Responsable cuando el Workspace lo permite. El objetivo de unicidad es:

`Tarea de catálogo + fecha planificada + Responsable`

La constraint V1 que omite Responsable no es el objetivo V2.

### 4.4 Ciclo de vida

Una Tarea pasa de Programada a Pendiente cuando llega su fecha. El usuario registra Completada o No Realizada. No se requiere historial de progreso o comentarios por Tarea. Los datos pasados se conservan salvo las correcciones y reclasificaciones expresamente aprobadas.

### 4.5 Creación recurrente finita

Se soporta creación diaria, semanal y mensual, siempre con Desde y Hasta obligatorios; no hay generación abierta o perpetua.

- Semanal: uno o varios días de semana.
- Mensual: uno o varios días de mes.
- Diaria: dentro del rango finito configurado.

Para los días 29, 30 o 31 inexistentes en un mes se usa el último día calendario y se muestra una advertencia explicativa. Si varios días configurados colapsan en la misma fecha, se crea una sola ocurrencia para la misma combinación de catálogo, fecha y Responsable.

## 5. Pendientes

Un Pendiente representa un asunto con seguimiento prolongado. Incluye Vigencia, nombre, Categoría, Responsable, fecha planificada, Avance, Estado, Cumplimiento, Detalle, fecha de cumplimiento y acciones.

El historial cronológico conserva las actualizaciones de seguimiento, como Fecha, Usuario o Responsable según corresponda, Avance y Comentario. `Última actualización` puede derivarse de la actualización más reciente; no exige un valor manual independiente. No se requiere un segundo sistema conversacional de comentarios.

Para Revisión, un Pendiente califica cuando está asignado al usuario actual, está Activo, no está finalizado y su fecha planificada es hoy o anterior.

En móvil se prioriza una representación vertical compacta. La información secundaria se abre mediante `>` en una página interna de detalle con flecha de retorno; no se expande debajo de una fila.

## 6. Proyectos y Etapas

Un Proyecto contiene información general y una colección de **Etapas**. En la interfaz no se usa Paso. El Proyecto incluye Vigencia, nombre, Categoría, Líder, fecha planificada, Avance, Estado, Cumplimiento, Detalle, fecha de cumplimiento y acciones.

Cada Etapa puede incluir Responsable, peso, fecha planificada, Avance, Estado, Cumplimiento, Detalle, fecha de cumplimiento y Comentario. Su historial cronológico conserva Fecha, Usuario, Avance y Comentario. No necesita Vigencia propia: la Vigencia del Proyecto gobierna su participación en los flujos pertinentes.

El Avance del Proyecto se agrega desde sus Etapas mediante el modelo de ponderación aprobado. Para Revisión, una Etapa califica cuando está asignada al usuario actual, su Proyecto está Activo, no está finalizada y su fecha planificada es hoy o anterior.

La navegación es jerárquica mediante páginas internas:

`Proyectos → > → detalle del Proyecto → Etapas → > → detalle de la Etapa`

Cada detalle ocupa el área blanca principal y ofrece una flecha de retorno. No se utilizan expansiones anidadas bajo la tabla general.

## 7. Catálogo de Actividades

V2 incorpora `Tablas → Actividades`, con nombre, Categoría, Vigencia Activa/Inactiva y acciones sujetas a reglas de uso. Solo las entradas Activas aparecen en el selector normal.

Al crear una Actividad se puede seleccionar una entrada del catálogo o elegir `Otra actividad` e ingresar nombre y Categoría manualmente. Una entrada del catálogo determina su Categoría automáticamente. Una Actividad libre conserva la Categoría explícita de su ocurrencia.

La Categoría de una Actividad basada en catálogo es dinámica: si cambia en el catálogo, sus ocurrencias y reportes históricos se reclasifican. Es la misma excepción histórica aprobada para Tareas.

## 8. Calendario y Actividades

Una Actividad es un bloque de tiempo de calendario. No tiene Responsable; puede tener Organizador y Participantes. El Organizador es quien la crea y es la única persona que puede modificarla o cancelarla para todos.

Al crearla se selecciona un Workspace. Los posibles Participantes son miembros de ese Workspace y su selección es opcional. No existe aceptación/rechazo: al añadir a una persona, la Actividad aparece automáticamente en su calendario.

Un Participante puede retirarla de su propio calendario sin eliminarla para los demás. Esto también desactiva su recordatorio individual asociado.

Las Actividades recurrentes usan generación finita diaria, semanal o mensual con Desde y Hasta, incluyendo la regla 29/30/31 y deduplicación. Las operaciones de serie no modifican el pasado. Las opciones simplificadas incluyen `Solo esta` y `Todas las futuras`; no se añade otra opción semánticamente redundante.

## 9. Mi calendario

Mi calendario es global: muestra las Actividades del usuario a través de todos sus Workspaces y no muestra el selector global. Puede diferenciarlas visualmente por Workspace sin añadir texto antiestético al nombre.

Presentación predeterminada:

- desktop: semanal;
- móvil: diaria;
- comparación: diaria.

El Calendario usa controles internos para seleccionar el Workspace y las personas cuando se realiza comparación colaborativa.

## 10. Privacidad y disponibilidad del Calendario

Para cada Workspace compartido pertinente, una persona configura cómo sus miembros pueden ver su calendario consolidado:

1. Mostrar detalles.
2. Solo disponibilidad.
3. Ocultar.

La política se aplica al calendario consolidado de la persona, no solo a las Actividades creadas dentro del Workspace compartido. Así se evita mostrar disponibilidad falsa durante Actividades personales o de otros Workspaces.

- **Mostrar detalles:** presenta datos de las Actividades autorizadas sin anexar `[Workspace]` a sus nombres.
- **Solo disponibilidad:** muestra bloques ocupados neutrales, sin detalles ni texto repetido Libre/Ocupado por intervalo.
- **Ocultar:** no muestra calendario y presenta un mensaje sencillo de privacidad.

La comparación abre una página interna separada, diaria, y compara solo miembros seleccionados que permiten visibilidad. No se anexa debajo del Calendario normal.

## 11. Revisión

Revisión es un flujo global, accesible en cualquier momento y sin selector global de Workspace. Los recordatorios no limitan su acceso por horario.

### 11.1 Tareas

Muestra las Tareas Pendientes asignadas al usuario actual con `Fecha | Workspace | Tarea | selector Completada/No Realizada`. El selector representa el resultado; no se añade una columna Resultado redundante.

### 11.2 Pendientes

Muestra `Fecha | Workspace | Pendiente | Avance | Comentario` para elementos elegibles según la sección 5.

### 11.3 Proyectos

Muestra `Fecha | Workspace | Proyecto | Etapa | Avance | Comentario` para Etapas elegibles según la sección 6.

Cada bloque se guarda independientemente: Tareas, Pendientes y Proyectos/Etapas. Este comportamiento puede evaluarse tras uso real, pero es la línea base V2 aprobada.

## 12. Inicio

Inicio es global, cruza Workspaces y no muestra el selector global. Resume el día y la información relevante sin convertirse en otra pantalla detallada de Seguimiento. Las métricas exactas se afinarán durante implementación y uso; no se consideran cerradas en esta etapa.

## 13. Centro de notificaciones y push

El centro de notificaciones dentro de la aplicación se abre como panel, modal u overlay sobre el contenido actual; no es una página completa. No genera notificaciones de “nuevo comentario”. Una serie larga produce una notificación lógica de creación/asignación, no una por ocurrencia.

La campana registra eventos que requieren atención directa de la persona afectada:

- invitación a un Workspace y aceptación o rechazo relevante para quien invita o administra;
- retiro de una persona de un Workspace cuando le afecta;
- transferencia de propiedad desde o hacia una persona;
- otros eventos administrativos o de membresía directamente relevantes;
- asignación, reasignación o retiro de responsabilidad en una Tarea, Pendiente o Etapa;
- asignación o cambio de Líder de Proyecto;
- incorporación a una Actividad, modificación o cancelación de una Actividad futura que involucra a la persona;
- retiro de un Participante de su propio calendario cuando resulte relevante para el Organizador.

Los siguientes recordatorios generan tanto push como una entrada en la campana:

- Recordatorio diario;
- Revisión diaria;
- Seguimiento de Pendientes;
- Seguimiento de Proyectos;
- recordatorios configurados de Actividades.

No se genera una notificación por cada ocurrencia de una serie, por comentarios nuevos ni por cambios rutinarios de avance que no requieran atención. Una operación recurrente masiva produce, cuando corresponde, una sola notificación lógica.

## 14. Recordatorios

### 14.1 Recordatorio diario

Es el resumen matutino de los elementos pertinentes del día, por ejemplo: “Para hoy tienes 2 tareas, 1 pendiente y 1 etapa de proyecto”. Es un comportamiento diario central, configurable como Activo y con hora —típicamente 07:00—, no un generador semanal o mensual arbitrario. Al pulsarlo, después de autenticar cuando sea necesario, abre Inicio.

### 14.2 Revisión diaria

Es el recordatorio vespertino para realizar Revisión, típicamente Activo a las 21:00 todos los días. Al pulsarlo abre Revisión. Es distinto de los recordatorios de Seguimiento.

### 14.3 Seguimiento de Pendientes y Proyectos

Son dos preferencias independientes para realizar barridos amplios desde sus pantallas de Seguimiento. Admiten frecuencia diaria, semanal con uno o varios días, o mensual con uno o varios días. No usan Desde/Hasta porque son preferencias persistentes editables.

Sus destinos son Seguimiento de Pendientes y Seguimiento de Proyectos respectivamente. Un recordatorio configurado de Actividad abre el contexto pertinente de Calendario/Actividad.

## 15. Reportes

Los Reportes permanecen deliberadamente flexibles. Se aprueba el concepto general de filtros compactos por Periodo, Responsable y Categoría; el Periodo puede usar última semana, último mes o rango personalizable. Las métricas exactas se refinarán con uso real y no se sobreespecifican.

Los Reportes son dependientes de Workspace cuando corresponde. Para Actividades deben permitir análisis por entrada del catálogo, Categoría y agregado `Otros` para Actividades libres, sin enumerar necesariamente cada nombre libre.

La Categoría histórica de Tareas y Actividades basadas en catálogo sigue siempre la Categoría actual de su entrada maestra.

## 16. UX móvil y navegación

Móvil vertical es un objetivo primario. Las pantallas densas priorizan campos esenciales, filas o tarjetas compactas, barras de Avance y páginas de detalle. No se toma una tabla desktop ancha como único diseño para luego depender de scroll horizontal.

Los filtros son compactos y no dominan el contenido. Desktop puede usar tablas más ricas.

Un control `>` abre una página interna en el área blanca, conserva la navegación verde y muestra una flecha de retorno. La creación simple mediante `+ Nueva` normalmente abre un modal compacto. Los detalles complejos usan páginas internas. El centro de notificaciones usa overlay, no página.

Los controles deshabilitados son legibles y visualmente atenuados, sin hover ni animación, y mantienen el cursor normal; no utilizan `not-allowed`.

## 17. Configuración

Configuración usa una estructura responsive sin una segunda barra lateral permanente dentro del área blanca. Incluye perfil, recordatorios, administración necesaria de Workspace/membresías, privacidad del Calendario, controles necesarios de cuenta/seguridad e información/versión de la aplicación.

No incluye selector de idioma ni submódulo de Configuración regional. Se mantienen `dd/mm/yyyy`, lunes como inicio de semana y las vistas predeterminadas de Calendario definidas anteriormente.

## 18. Retiro de miembros

Al retirar a un miembro de un Workspace compartido, los datos pasados permanecen congelados y conservan autoría e historia.

Para Tareas, Pendientes y Etapas futuras, el flujo permite a la persona Propietaria o administradora reasignar o eliminar un elemento futuro. Cuando existe contenido repetido o en serie, permite eliminar la ocurrencia seleccionada o las ocurrencias futuras relacionadas. También ofrece `Eliminar todo` para las responsabilidades o el contenido futuro pertinente de la persona retirada. La reasignación no es obligatoria.

Las Actividades pasadas no cambian. En Actividades futuras se retira a la persona de Participantes. Si era Organizadora, puede conservarse su atribución histórica; V2 no exige reasignar al Organizador.

Una persona Propietaria no puede abandonar el Workspace mientras conserve esa condición: primero debe transferir la propiedad. La secuencia transaccional, el comportamiento exacto de claves foráneas y otros detalles de persistencia pertenecen al diseño técnico.

## 19. Seguridad

Seguridad es requisito transversal de V2 y tendrá un gate final antes de producción. El flujo funcional de acceso restringido es: solicitud de registro → validación anti-bot mediante Cloudflare Turnstile → creación del estado de cuenta necesario → verificación de correo → espera de aprobación global → aprobación por `GLOBAL_ADMIN` → activación de la cuenta → acceso a LifeManager.

Los requisitos aprobados incluyen:

- solicitud de registro restringida y aprobación por administrador global;
- verificación de correo y recuperación de contraseña;
- separación de rol global y rol de Workspace;
- contraseña mínima de ocho caracteres, con mayúscula, minúscula y símbolo;
- rate limiting, protección contra fuerza bruta y Cloudflare Turnstile o protección anti-bot equivalente;
- autorización server-side, aislamiento de usuario y Workspace;
- arquitectura de sesión segura;
- secretos ausentes del frontend, source y respuestas;
- validación server-side, protección de mass assignment y consultas parametrizadas;
- prevención de XSS/inyección de contenido y respuestas API mínimas;
- CORS, CSP, security headers y HTTPS/TLS;
- revisión de dependencias, SAST, SCA y cadena de suministro;
- seguridad de Neon, Render, Cloudflare y GitHub;
- pruebas de seguridad explícitas.

La recuperación de contraseña devuelve respuestas neutrales que no revelan si una cuenta existe. Permanecen pendientes únicamente detalles técnicos como el proveedor de correo, la representación física de estados de cuenta y la implementación concreta de tokens y sesiones.

PostgreSQL RLS debe evaluarse como defensa en profundidad; no se impone sin análisis arquitectónico.

## 20. Inmutabilidad e historia

Las operaciones sobre series, membresías o contenido futuro no reescriben silenciosamente registros históricos. Las excepciones aprobadas son la reclasificación dinámica por Categoría actual de las entradas maestras de Tareas y Actividades y las correcciones explícitas que se definan por dominio.

Pendientes y Etapas conservan un historial cronológico de seguimiento; no se exige un sistema conversacional separado.

## 21. Transición desde V1

La línea base formal es el tag anotado `v1.0.0`, cuyo commit es `fafa8844f83763c837aa423d0773cd6d5782752c`.

Los datos V1 actuales son exclusivamente de prueba/no esenciales y no necesitan preservarse durante el desarrollo V2. Un reset destructivo controlado puede elegirse en la etapa técnica, pero no está autorizado por este documento ni debe ejecutarse ahora. El historial Git y Alembic se conserva.

Después de publicar V2.0.0 y comenzar uso real, los datos de producción se consideran valiosos y las migraciones futuras deberán preservarlos.

## 22. Fuera de alcance y asuntos deliberadamente abiertos

No se añaden funciones especulativas V3 ni multilenguaje. Permanecen abiertos únicamente:

- métricas exactas de Inicio y Reportes;
- modelo físico, contratos API y transacciones V2;
- matriz completa de permisos por rol;
- proveedor de correo, representación física de estados de cuenta e implementación de tokens/sesiones del registro restringido;
- secuencia transaccional y comportamiento de persistencia para retiro de miembros y contenido futuro.

Estos puntos requieren diseño posterior o validación de producto; no invalidan las decisiones funcionales cerradas.
