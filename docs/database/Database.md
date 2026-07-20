# Base de datos de LifeManager

## 1. Propósito

Este documento describe el diseño general de la base de datos de LifeManager, las tecnologías utilizadas, las entidades principales y las reglas que deberán respetarse durante su desarrollo.

La base de datos deberá soportar una aplicación:

- colaborativa;
- escalable;
- modular;
- multiusuario;
- segura.

---

## 2. Tecnología

LifeManager utilizará PostgreSQL como sistema de gestión de base de datos relacional.

El backend accederá a PostgreSQL mediante:

- Psycopg como controlador;
- SQLAlchemy 2.x como ORM;
- Alembic para la gestión de migraciones.

---

## 3. Base de datos actual

El nombre actual de la base de datos de desarrollo es:

```text
lifemanager
```

La configuración de conexión se obtiene mediante variables de entorno.

Ejemplo:

```text
DB_HOST
DB_NAME
DB_PASSWORD
DB_PORT
DB_USER
```

Los valores reales deberán permanecer en:

```text
backend/.env
```

El archivo `.env` no deberá subirse a GitHub.

---

## 4. Principios generales

El diseño de la base de datos seguirá estos principios:

- evitar duplicación innecesaria;
- mantener integridad referencial;
- permitir crecimiento modular;
- priorizar relaciones explícitas;
- utilizar restricciones para proteger la consistencia;
- utilizar tipos de datos adecuados;
- conservar historial cuando sea necesario.

---

## 5. Convenciones generales

### Claves primarias

Las entidades principales utilizarán UUID como clave primaria.

Ejemplo:

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid.uuid4,
)
```

Ventajas:

- evita exponer secuencias predecibles;
- facilita la creación distribuida de registros;
- reduce conflictos durante futuras integraciones;
- permite identificar registros de forma global.

### Claves foráneas

Las claves foráneas deberán declararse explícitamente.

Ejemplo:

```python
workspace_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("workspaces.id"),
    nullable=False,
)
```

### Nombres de columnas

Los nombres de columnas deberán utilizar:

```text
snake_case
```

Ejemplos:

```text
created_at
full_name
password_hash
workspace_id
```

### Nombres de tablas

Los nombres de tablas deberán:

- escribirse en plural;
- utilizar `snake_case`;
- representar claramente la entidad almacenada.

Ejemplos:

```text
task_occurrences
users
workspace_members
workspaces
```

---

## 6. Base común de entidades

Los modelos principales heredarán de una clase abstracta común:

```text
BaseEntity
```

Inicialmente, esta clase proporcionará:

- `created_at`;
- `id`;
- `updated_at`.

La clase no representará una tabla propia en PostgreSQL.

Ejemplo conceptual:

```text
BaseEntity
├── created_at
├── id
└── updated_at
```

Los modelos concretos heredarán esas columnas:

```text
BaseEntity
├── User
├── Workspace
└── WorkspaceMember
```

---

## 7. Marcas de tiempo

Las entidades principales deberán incluir:

```text
created_at
updated_at
```

### created_at

Indica cuándo se creó el registro.

Deberá asignarse automáticamente desde la base de datos.

### updated_at

Indica cuándo se modificó por última vez el registro.

Deberá actualizarse cuando el registro cambie.

Las fechas deberán almacenarse con soporte de zona horaria.

---

## 8. Eliminación lógica

LifeManager podrá utilizar eliminación lógica o `soft delete` en entidades donde sea necesario conservar historial.

La columna prevista es:

```text
deleted_at
```

Cuando sea `NULL`, el registro se considerará activo.

Cuando tenga una fecha, el registro se considerará eliminado lógicamente.

Ejemplo:

```text
deleted_at = NULL
```

Registro activo.

```text
deleted_at = 2026-07-20 14:30:00
```

Registro eliminado lógicamente.

La decisión definitiva sobre qué entidades utilizarán esta estrategia deberá documentarse antes de su implementación general.

No todas las tablas necesitarán eliminación lógica.

---

## 9. Entidades actuales

### User

Representa una cuenta de usuario de LifeManager.

Campos previstos o implementados:

- `created_at`;
- `email`;
- `full_name`;
- `id`;
- `is_active`;
- `is_verified`;
- `language`;
- `password_hash`;
- `timezone`;
- `updated_at`;
- `username`.

Responsabilidades:

- almacenar la identidad del usuario;
- almacenar preferencias generales;
- permitir autenticación;
- relacionarse con uno o varios workspaces.

### Workspace

Representa un espacio donde se organizan y comparten recursos.

Ejemplos:

```text
Familia Natividad
Personal
Trabajo
```

Campos iniciales:

- `created_at`;
- `description`;
- `id`;
- `name`;
- `updated_at`.

Responsabilidades:

- agrupar información;
- separar datos entre contextos;
- permitir colaboración;
- servir como propietario lógico de futuros recursos.

### WorkspaceMember

Representa la relación entre un usuario y un workspace.

Campos iniciales:

- `created_at`;
- `id`;
- `role`;
- `updated_at`;
- `user_id`;
- `workspace_id`.

Responsabilidades:

- determinar si un usuario pertenece a un workspace;
- establecer su rol;
- permitir relaciones de muchos a muchos;
- servir como base para la autorización.

---

## 10. Relaciones actuales

La relación principal es:

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

Un usuario puede pertenecer a varios workspaces.

Un workspace puede contener varios usuarios.

La tabla intermedia es:

```text
workspace_members
```

Relación conceptual:

```text
users
   │
   └── workspace_members
            └── workspaces
```

---

## 11. Restricciones de WorkspaceMember

La combinación de:

```text
user_id
workspace_id
```

deberá ser única.

Esto impedirá que un mismo usuario sea agregado dos veces al mismo workspace.

Restricción prevista:

```text
UNIQUE (user_id, workspace_id)
```

También deberán existir índices para:

- `user_id`;
- `workspace_id`.

Esto permitirá consultar eficientemente:

- los miembros de un workspace;
- los workspaces de un usuario.

---

## 12. Roles de workspace

Inicialmente se utilizarán los siguientes roles:

```text
ADMIN
MEMBER
OWNER
VIEWER
```

Los roles se almacenarán mediante un tipo enumerado.

### ADMIN

Puede administrar recursos y miembros según las reglas definidas.

### MEMBER

Puede participar y gestionar recursos permitidos.

### OWNER

Tiene el nivel máximo de control dentro del workspace.

### VIEWER

Tiene acceso principalmente de lectura.

Los permisos exactos se documentarán en:

```text
docs/architecture/Permissions.md
```

---

## 13. Reglas del workspace personal

Cuando se implemente el registro de usuarios, se deberá ejecutar una única transacción que:

1. cree el usuario;
2. cree su workspace personal;
3. cree el registro `WorkspaceMember`;
4. asigne el rol `OWNER`.

Si una de estas operaciones falla, ninguna deberá confirmarse.

Ejemplo conceptual:

```text
BEGIN

Crear User
Crear Workspace
Crear WorkspaceMember

COMMIT
```

En caso de error:

```text
ROLLBACK
```

Esto evitará usuarios incompletos o sin workspace personal.

---

## 14. Propiedad de los datos

Los recursos funcionales deberán pertenecer principalmente a un workspace.

Ejemplos futuros:

```text
categories.workspace_id
task_templates.workspace_id
```

Esto permitirá:

- compartir recursos;
- separar información personal y familiar;
- filtrar datos según el workspace activo;
- administrar permisos de manera consistente.

Cuando sea necesario conocer al creador de un recurso, se podrá utilizar una columna adicional como:

```text
created_by_user_id
```

La pertenencia al workspace y la autoría del recurso son conceptos diferentes.

---

## 15. Entidades previstas para tareas

El primer módulo funcional utilizará inicialmente estas entidades:

### Category

Permitirá clasificar tareas dentro de un workspace.

### TaskOccurrence

Representará una ejecución concreta de una tarea en una fecha específica.

### TaskResponse

Registrará el resultado o respuesta del usuario ante una tarea.

### TaskTemplate

Definirá una tarea reutilizable o recurrente.

Relación conceptual inicial:

```text
Workspace
   │
   ├── Category
   │
   └── TaskTemplate
            │
            └── TaskOccurrence
                     │
                     └── TaskResponse
```

El diseño definitivo se realizará antes de crear estas tablas.

---

## 16. Estados y enumeraciones

Cuando una columna tenga un conjunto cerrado y estable de valores, podrá utilizarse un `Enum`.

Ejemplos:

```text
WorkspaceRole
TaskStatus
```

Los valores de una enumeración deberán:

- tener nombres claros;
- mantenerse consistentes;
- documentarse;
- evitar cambios frecuentes.

Cuando se prevea que los valores serán configurables por los usuarios, deberá utilizarse una tabla en lugar de un `Enum`.

---

## 17. Campos obligatorios y opcionales

Todas las columnas deberán declarar explícitamente si aceptan valores nulos.

Ejemplo obligatorio:

```python
name: Mapped[str] = mapped_column(
    String(150),
    nullable=False,
)
```

Ejemplo opcional:

```python
description: Mapped[str | None] = mapped_column(
    String(500),
    nullable=True,
)
```

No se deberá depender únicamente del comportamiento predeterminado de SQLAlchemy.

---

## 18. Longitudes de texto

Los campos de texto corto deberán tener límites razonables.

Ejemplos iniciales:

```text
email: 320 caracteres
full_name: 150 caracteres
name: 150 caracteres
username: 50 caracteres
```

Los textos extensos podrán utilizar el tipo `Text`.

Las longitudes definitivas deberán definirse según el propósito de cada campo.

---

## 19. Índices

Deberán crearse índices para columnas utilizadas frecuentemente en:

- búsquedas;
- filtros;
- relaciones;
- validaciones de unicidad.

Ejemplos:

```text
users.email
users.username
workspace_members.user_id
workspace_members.workspace_id
```

No se crearán índices sin una necesidad clara, porque también aumentan el costo de escritura y almacenamiento.

---

## 20. Restricciones de unicidad

Las restricciones de unicidad protegen la consistencia de los datos.

Inicialmente se consideran:

```text
users.email
users.username
workspace_members (user_id, workspace_id)
```

La validación deberá existir tanto en:

- la aplicación;
- la base de datos.

La base de datos será la última línea de protección.

---

## 21. Borrado y relaciones

Cada clave foránea deberá definir conscientemente qué ocurre cuando se elimina el registro relacionado.

Opciones posibles:

```text
CASCADE
RESTRICT
SET NULL
```

### CASCADE

Elimina registros dependientes automáticamente.

### RESTRICT

Impide eliminar un registro si existen dependencias.

### SET NULL

Mantiene el registro dependiente y elimina la referencia.

No se utilizará `CASCADE` automáticamente en todas las relaciones.

Cada caso deberá analizarse según el riesgo de pérdida de datos.

---

## 22. Sesiones y transacciones

El acceso a la base de datos utilizará sesiones de SQLAlchemy.

La lógica de negocio deberá controlar adecuadamente:

- `commit`;
- `rollback`;
- cierre de sesiones;
- manejo de excepciones.

Las operaciones compuestas deberán ejecutarse dentro de una transacción.

Ejemplos:

- crear un usuario con su workspace personal;
- eliminar lógicamente un workspace y sus recursos;
- agregar un miembro y asignarle permisos;
- crear una tarea recurrente con sus configuraciones.

---

## 23. Migraciones

Alembic será la única herramienta oficial para modificar el esquema de la base de datos.

No deberán realizarse cambios manuales directamente en PostgreSQL salvo para diagnóstico o desarrollo controlado.

Flujo previsto:

```text
Modificar modelos
   │
   ▼
Generar migración
   │
   ▼
Revisar migración
   │
   ▼
Aplicar migración
   │
   ▼
Verificar base de datos
```

Los detalles se documentarán en:

```text
docs/database/Migrations.md
```

---

## 24. Datos sensibles

Nunca deberán almacenarse contraseñas en texto plano.

Se almacenará únicamente:

```text
password_hash
```

Otros datos sensibles deberán protegerse mediante:

- acceso restringido;
- configuración segura;
- cifrado cuando sea necesario;
- exclusión de registros y respuestas innecesarias.

La base de datos no deberá almacenar secretos de aplicación directamente dentro de las tablas comunes.

---

## 25. Zonas horarias

Las fechas importantes deberán almacenarse con zona horaria.

Preferentemente, el sistema trabajará internamente con UTC.

Cada usuario podrá tener configurada una zona horaria mediante:

```text
users.timezone
```

El frontend mostrará las fechas convertidas a la zona horaria correspondiente.

Esto será especialmente importante para:

- notificaciones;
- tareas programadas;
- hábitos diarios;
- fechas límite;
- reportes.

---

## 26. Integridad de los datos

La integridad deberá protegerse mediante:

- claves foráneas;
- restricciones de unicidad;
- tipos de datos adecuados;
- transacciones;
- validaciones de Pydantic;
- validaciones de servicios;
- valores no nulos cuando corresponda.

La lógica del frontend no será suficiente para proteger la integridad.

---

## 27. Rendimiento

Durante las primeras etapas se priorizará un diseño correcto y claro.

Las optimizaciones se aplicarán cuando existan datos o mediciones que las justifiquen.

Posibles herramientas futuras:

- análisis de consultas;
- caché;
- paginación;
- índices adicionales;
- consultas agregadas;
- vistas materializadas.

No se optimizará prematuramente.

---

## 28. Copias de seguridad

Antes de utilizar LifeManager con datos reales, se deberá definir una estrategia de respaldo.

La estrategia deberá considerar:

- frecuencia;
- restauración;
- retención;
- seguridad;
- verificación de respaldos.

Esta parte se definirá junto con el despliegue de producción.

---

## 29. Estado actual

### Implementado

- Base de datos `lifemanager`.
- Conexión mediante Psycopg.
- Configuración mediante variables de entorno.
- Migraciones mediante Alembic.
- Modelo `User`.
- SQLAlchemy 2.x.
- Tabla `alembic_version`.
- Tabla `users`.

### En proceso

- BaseEntity.
- Modelo `Workspace`.
- Modelo `WorkspaceMember`.
- Restricciones e índices del núcleo colaborativo.

### Pendiente

- Aplicar la migración de workspaces.
- Definir reglas de eliminación.
- Definir relaciones bidireccionales.
- Implementar autenticación.
- Implementar schemas.
- Implementar services.
- Implementar transacciones de registro.
- Modelar el módulo de tareas.