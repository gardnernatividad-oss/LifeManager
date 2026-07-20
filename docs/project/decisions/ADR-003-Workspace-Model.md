# ADR-003: Modelo de workspaces y membresías

## Estado

Aceptado.

## Fecha

2026-07-20

---

## Contexto

LifeManager debe permitir que una misma persona gestione información personal y también participe en espacios compartidos con familiares, equipos u otros grupos.

El sistema necesita resolver desde el inicio las siguientes necesidades:

- un usuario puede participar en varios espacios;
- un espacio puede tener varios usuarios;
- cada usuario puede tener un rol distinto dentro de cada espacio;
- los recursos colaborativos deben quedar aislados por espacio;
- debe existir una base sólida para implementar permisos;
- cada usuario debe contar con un espacio personal;
- en el futuro podrán existir espacios familiares, laborales o de otros tipos.

Era necesario decidir cómo representar la relación entre usuarios y espacios de trabajo.

---

## Decisión

LifeManager utilizará tres entidades principales:

- `User`
- `Workspace`
- `WorkspaceMember`

La relación entre usuarios y workspaces será de muchos a muchos y se representará mediante la entidad asociativa `WorkspaceMember`.

```text
User
   │
   │ 1
   ▼
WorkspaceMember
   ▲
   │ 1
   │
Workspace
```

Desde la perspectiva completa:

```text
User
   │
   │ muchos
   ▼
WorkspaceMember
   ▲
   │ muchos
   │
Workspace
```

`WorkspaceMember` no será únicamente una tabla técnica de unión. Será una entidad del dominio con información propia.

Inicialmente almacenará:

- `created_at`;
- `id`;
- `role`;
- `updated_at`;
- `user_id`;
- `workspace_id`.

En el futuro podrá incluir otros campos relacionados con la membresía.

---

## Modelo de usuario

`User` representará una cuenta individual dentro de LifeManager.

Un usuario podrá:

- tener un workspace personal;
- crear otros workspaces;
- pertenecer a workspaces compartidos;
- tener roles diferentes en cada workspace;
- abandonar determinados workspaces;
- acceder únicamente a los recursos para los que tenga autorización.

La cuenta del usuario y su participación en un workspace serán conceptos separados.

---

## Modelo de workspace

`Workspace` representará el límite principal de organización, colaboración y propiedad lógica de los datos.

Ejemplos:

```text
Familia Natividad
Personal
Proyecto de construcción
Trabajo
```

Un workspace podrá contener:

- categorías;
- configuraciones;
- hábitos;
- miembros;
- metas;
- notificaciones;
- proyectos;
- tareas;
- otros recursos futuros.

Los recursos compartidos deberán pertenecer principalmente a un workspace mediante una clave foránea.

Ejemplo:

```text
task_templates.workspace_id
```

---

## Modelo de membresía

`WorkspaceMember` representará la participación de un usuario dentro de un workspace específico.

Permitirá almacenar información que depende de esa relación y no únicamente del usuario o del workspace.

Ejemplos:

- rol;
- fecha de incorporación;
- estado de la membresía;
- preferencias dentro del workspace;
- permisos especiales;
- usuario que realizó la invitación.

Aunque no todos estos campos se implementarán inicialmente, el modelo permite agregarlos en el futuro sin rediseñar la relación.

---

## Workspace personal

Cada usuario deberá tener al menos un workspace personal.

Cuando se implemente el registro, la creación de la cuenta deberá realizar una transacción que:

1. cree el usuario;
2. cree su workspace personal;
3. cree su membresía;
4. asigne el rol `OWNER`.

Flujo:

```text
Crear User
   │
   ▼
Crear Workspace personal
   │
   ▼
Crear WorkspaceMember
   │
   ▼
Asignar OWNER
```

Estas operaciones deberán ejecutarse dentro de una misma transacción.

Si una de ellas falla, todas deberán revertirse.

---

## Roles iniciales

Los roles iniciales serán:

- `ADMIN`
- `MEMBER`
- `OWNER`
- `VIEWER`

### ADMIN

Podrá administrar recursos y miembros de acuerdo con las reglas del sistema.

No deberá tener automáticamente todas las capacidades exclusivas del propietario.

### MEMBER

Podrá participar en el workspace y gestionar los recursos autorizados.

### OWNER

Será el propietario principal del workspace.

Tendrá el nivel más alto de control y será responsable de operaciones críticas.

### VIEWER

Tendrá acceso principalmente de lectura.

Los permisos exactos de cada rol se definirán en:

```text
docs/architecture/Permissions.md
```

---

## Restricciones

La combinación de:

```text
user_id
workspace_id
```

deberá ser única.

Restricción:

```text
UNIQUE (user_id, workspace_id)
```

Esto impedirá que el mismo usuario tenga dos membresías activas duplicadas dentro del mismo workspace.

También deberán existir claves foráneas desde `WorkspaceMember` hacia:

```text
users.id
workspaces.id
```

---

## Índices

Se crearán índices para:

```text
workspace_members.user_id
workspace_members.workspace_id
```

Estos índices permitirán consultar eficientemente:

- todos los workspaces de un usuario;
- todos los miembros de un workspace;
- la membresía de un usuario dentro de un workspace;
- el rol de un usuario dentro de un workspace.

---

## Propiedad y autoría de los recursos

La pertenencia de un recurso a un workspace y la identidad de su creador serán conceptos diferentes.

Ejemplo:

```text
workspace_id
created_by_user_id
```

`workspace_id` indicará el contexto al que pertenece el recurso.

`created_by_user_id` indicará quién lo creó.

No todos los recursos necesitarán almacenar el creador, pero los recursos colaborativos deberán pertenecer a un workspace.

---

## Autorización

La autorización se basará inicialmente en:

1. el usuario autenticado;
2. la existencia de una membresía activa;
3. el rol del usuario dentro del workspace;
4. las reglas específicas del recurso o módulo.

Flujo conceptual:

```text
Solicitud
   │
   ▼
Identificar usuario
   │
   ▼
Identificar workspace
   │
   ▼
Buscar WorkspaceMember
   │
   ▼
Verificar rol y permiso
   │
   ▼
Permitir o rechazar
```

El frontend podrá ocultar acciones no permitidas, pero la validación definitiva deberá ocurrir siempre en el backend.

---

## Alternativas consideradas

### Asociar todos los datos directamente al usuario

Se consideró almacenar cada tarea, hábito o recurso directamente mediante:

```text
user_id
```

Esta alternativa fue descartada porque dificultaría:

- compartir recursos;
- crear espacios familiares;
- implementar equipos;
- separar contextos;
- administrar permisos;
- transferir propiedad;
- colaborar en proyectos.

### Guardar una lista de usuarios dentro del workspace

Se consideró almacenar miembros como una lista o campo compuesto dentro de `Workspace`.

Fue descartado porque:

- dificultaría aplicar integridad referencial;
- complicaría consultas;
- dificultaría asignar roles;
- impediría almacenar información propia de cada membresía;
- no representaría adecuadamente una relación muchos a muchos.

### Usar únicamente una tabla de unión sin identidad propia

Se consideró utilizar una tabla mínima compuesta solo por:

```text
user_id
workspace_id
```

Fue descartado porque la relación necesita almacenar al menos un rol y probablemente más información en el futuro.

### Crear modelos separados para espacios personales y compartidos

Se consideró utilizar entidades diferentes para:

- espacios personales;
- espacios familiares;
- espacios de equipo.

Fue descartado porque duplicaría lógica y estructuras.

Todos se representarán mediante `Workspace`, cambiando únicamente sus miembros, configuración o tipo cuando sea necesario.

---

## Consecuencias positivas

- Soporte multiusuario desde el núcleo.
- Separación clara entre cuenta y contexto de trabajo.
- Posibilidad de crear workspaces personales y compartidos.
- Roles diferentes para un mismo usuario en distintos workspaces.
- Base sólida para permisos y autorización.
- Propiedad lógica consistente de los recursos.
- Escalabilidad hacia familias, equipos y proyectos.
- Posibilidad de añadir información a la membresía.
- Consultas claras mediante relaciones relacionales.

---

## Consecuencias negativas

- Todas las consultas de recursos deberán considerar el workspace.
- La autorización será más compleja que en una aplicación de un solo usuario.
- Será necesario administrar invitaciones y membresías.
- Se deberán evitar filtraciones de datos entre workspaces.
- La creación de usuarios requerirá una transacción adicional.
- El sistema deberá manejar casos como abandono, eliminación o transferencia de propiedad.

---

## Riesgos

- Consultar recursos sin filtrar por `workspace_id`.
- Permitir acceso sin validar `WorkspaceMember`.
- Asignar capacidades excesivas al rol `ADMIN`.
- Eliminar un workspace sin controlar sus dependencias.
- Permitir que un workspace quede sin propietario.
- Crear membresías duplicadas.
- Mezclar la autoría de un recurso con su propiedad.
- Implementar permisos únicamente en el frontend.

---

## Reglas derivadas

A partir de esta decisión:

1. Los recursos colaborativos deberán pertenecer a un workspace.
2. Un usuario podrá pertenecer a varios workspaces.
3. Un workspace podrá tener varios usuarios.
4. La relación se representará mediante `WorkspaceMember`.
5. Cada membresía deberá tener un rol.
6. La combinación `user_id` y `workspace_id` deberá ser única.
7. La autorización deberá validar la membresía en el backend.
8. Cada nuevo usuario deberá recibir un workspace personal.
9. La creación del usuario y su workspace personal deberá ser transaccional.
10. Un workspace deberá conservar al menos un propietario activo.
11. La propiedad del recurso y la autoría deberán modelarse por separado cuando corresponda.
12. Cualquier cambio importante en este modelo deberá registrarse mediante un nuevo ADR.

---

## Documentos relacionados

- `docs/architecture/Architecture.md`
- `docs/architecture/Permissions.md`
- `docs/database/Database.md`
- `docs/database/ERD.md`
- `docs/project/ProjectContext.md`
- `docs/project/Roadmap.md`

---

## Revisión futura

Esta decisión deberá revisarse si:

- se implementan organizaciones con estructuras jerárquicas;
- se necesitan permisos personalizados por miembro;
- aparecen subgrupos dentro de un workspace;
- se requiere más de un tipo de propietario;
- se introduce facturación por workspace;
- se necesitan equipos internos;
- el modelo actual deja de representar correctamente la colaboración.