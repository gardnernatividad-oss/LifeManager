# Arquitectura de LifeManager

## 1. Propósito

Este documento describe la arquitectura general de LifeManager, sus componentes principales, responsabilidades y reglas de diseño.

La arquitectura busca permitir que LifeManager crezca desde una aplicación de gestión de tareas hasta una plataforma modular de productividad personal, familiar y colaborativa.

---

## 2. Tipo de aplicación

LifeManager será una aplicación web progresiva, conocida como PWA.

La aplicación podrá:

- adaptarse a diferentes tamaños de pantalla;
- ejecutarse desde un navegador;
- enviar notificaciones;
- funcionar como una aplicación móvil sin necesitar inicialmente una aplicación nativa;
- instalarse en computadoras y teléfonos.

---

## 3. Arquitectura general

LifeManager utilizará una arquitectura cliente-servidor.

```text
Usuario
   │
   ▼
Frontend
Next.js
   │
   │ HTTP / API REST
   ▼
Backend
FastAPI
   │
   ▼
PostgreSQL
```

Cada componente tendrá responsabilidades claramente separadas.

### Frontend

El frontend será responsable de:

- administrar el estado visual de la aplicación;
- consumir la API;
- gestionar la navegación y los formularios;
- mostrar la interfaz de usuario;
- permitir la instalación como PWA;
- validar información básica antes de enviarla.

### Backend

El backend será responsable de:

- autenticación;
- autorización;
- exposición de endpoints mediante una API REST;
- gestión de espacios de trabajo;
- gestión de permisos;
- gestión de usuarios;
- lectura y escritura en la base de datos;
- lógica de negocio;
- validación de datos.

### Base de datos

PostgreSQL será responsable de almacenar de forma persistente:

- configuración de la aplicación;
- espacios de trabajo;
- hábitos;
- miembros;
- notificaciones;
- objetivos;
- permisos;
- respuestas;
- tareas;
- usuarios.

---

## 4. Stack tecnológico

### Backend

- Alembic
- FastAPI
- PostgreSQL
- Psycopg
- Pydantic
- Pydantic Settings
- Python
- SQLAlchemy 2.x
- Uvicorn

### Frontend

- Next.js
- React
- TypeScript

Las librerías adicionales del frontend se decidirán cuando comience su implementación.

### Herramientas de desarrollo

- Git
- GitHub
- PostgreSQL
- Visual Studio Code

---

## 5. Arquitectura modular

LifeManager se dividirá en módulos funcionales.

Cada módulo tendrá sus propios:

- documentación;
- endpoints;
- modelos;
- reglas de negocio;
- schemas;
- servicios.

Los módulos compartirán una infraestructura común:

- autenticación;
- base de datos;
- configuración;
- notificaciones;
- permisos;
- usuarios;
- workspaces.

### Núcleo inicial

El núcleo inicial estará formado por:

- User
- Workspace
- WorkspaceMember

### Primer módulo funcional

El primer módulo funcional será la gestión de tareas.

Inicialmente incluirá:

- Category
- TaskOccurrence
- TaskResponse
- TaskTemplate

### Módulos futuros

- Calendario
- Documentos
- Finanzas
- Hábitos
- Metas
- Notas
- Proyectos

Estos módulos todavía no están implementados y su diseño podrá cambiar.

---

## 6. Modelo multiusuario

LifeManager será multiusuario desde su primera versión.

Cada persona tendrá una cuenta representada por la entidad:

```text
User
```

Los datos colaborativos no pertenecerán directamente a un usuario. Pertenecerán principalmente a un espacio de trabajo:

```text
Workspace
```

La relación entre usuarios y espacios de trabajo se representará mediante:

```text
WorkspaceMember
```

Esto permitirá que un usuario pertenezca a varios espacios de trabajo.

Ejemplo:

```text
User
Gardner
   │
   ├── Workspace Familia Natividad
   └── Workspace Personal
```

Un workspace podrá tener varios miembros:

```text
Workspace Familia Natividad
   │
   ├── Gardner
   ├── Miembro 2
   └── Miembro 3
```

---

## 7. Workspace personal

Cuando se implemente el registro de usuarios, el flujo previsto será:

```text
Crear usuario
   │
   ▼
Crear workspace personal
   │
   ▼
Crear WorkspaceMember
   │
   ▼
Asignar rol OWNER
```

Cada usuario deberá tener al menos un workspace personal.

Los workspaces adicionales podrán utilizarse para familias, equipos, grupos u otras formas de colaboración.

---

## 8. Roles de workspace

La arquitectura contempla inicialmente los siguientes roles:

- ADMIN
- MEMBER
- OWNER
- VIEWER

### ADMIN

Podrá administrar gran parte del workspace, pero no necesariamente realizar acciones exclusivas del propietario.

### MEMBER

Podrá crear y gestionar recursos según las reglas del módulo.

### OWNER

Será el responsable principal del workspace.

Tendrá control completo sobre:

- configuración;
- desactivación;
- miembros;
- permisos;
- recursos.

### VIEWER

Tendrá acceso principalmente de lectura.

Las capacidades exactas de cada rol se definirán en:

```text
docs/architecture/Permissions.md
```

---

## 9. Arquitectura del backend

El backend seguirá una separación por responsabilidades.

```text
backend/
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── __init__.py
│   └── main.py
├── .env
├── alembic.ini
└── requirements.txt
```

### api

Contendrá las rutas y endpoints de FastAPI.

Los endpoints deberán encargarse principalmente de:

- llamar a servicios;
- recibir solicitudes;
- devolver respuestas HTTP;
- validar parámetros.

No deberán contener lógica de negocio extensa.

### core

Contendrá configuración e infraestructura transversal.

Ejemplos:

- configuración general;
- constantes;
- manejo de excepciones;
- seguridad;
- variables de entorno.

### db

Contendrá la configuración de acceso a la base de datos.

Ejemplos:

- dependencias de base de datos;
- engine;
- pruebas de conexión;
- sesiones.

### models

Contendrá los modelos de SQLAlchemy.

Cada modelo representará principalmente una tabla o estructura persistente.

### schemas

Contendrá los schemas de Pydantic.

Se utilizarán para:

- entrada de datos;
- salida de datos;
- serialización;
- validación.

Los schemas no deben confundirse con los modelos de SQLAlchemy.

### services

Contendrá la lógica de negocio.

Ejemplos:

- añadir miembros;
- crear un usuario y su workspace personal;
- programar tareas recurrentes;
- registrar cumplimiento;
- validar permisos.

---

## 10. Flujo de una solicitud

El flujo esperado será:

```text
Frontend
   │
   ▼
Endpoint de FastAPI
   │
   ▼
Schema de validación
   │
   ▼
Service
   │
   ▼
Modelo SQLAlchemy
   │
   ▼
PostgreSQL
```

La respuesta seguirá el flujo inverso:

```text
PostgreSQL
   │
   ▼
Modelo SQLAlchemy
   │
   ▼
Schema de respuesta
   │
   ▼
Endpoint
   │
   ▼
Frontend
```

---

## 11. Base de datos y ORM

LifeManager utilizará SQLAlchemy 2.x como ORM.

Las migraciones se administrarán con Alembic.

Reglas iniciales:

- claves foráneas explícitas;
- claves primarias UUID;
- columnas declaradas con `mapped_column`;
- modelos con tipado mediante `Mapped`;
- nombres de tablas en plural;
- nombres internos en `snake_case`;
- relaciones declaradas con `relationship`.

Los detalles se documentarán en:

```text
docs/database/Database.md
docs/database/Migrations.md
docs/database/NamingConventions.md
```

---

## 12. API

Inicialmente, el backend expondrá una API REST.

Las rutas se organizarán por recurso.

Ejemplos futuros:

```text
/api/v1/auth
/api/v1/tasks
/api/v1/users
/api/v1/workspace-members
/api/v1/workspaces
```

La versión inicial de la API será:

```text
v1
```

El prefijo definitivo se configurará cuando se implemente la estructura de rutas.

---

## 13. Autenticación y autorización

La autenticación permitirá identificar al usuario.

La autorización determinará qué acciones puede realizar dentro de cada workspace.

La seguridad deberá considerar:

- almacenamiento seguro de contraseñas;
- expiración de sesiones;
- restricción de recursos por workspace;
- tokens de acceso;
- validación de miembros;
- validación de roles.

La implementación definitiva se documentará en:

```text
docs/architecture/Authentication.md
docs/architecture/Permissions.md
```

---

## 14. Frontend

El frontend se desarrollará con Next.js, React y TypeScript.

Tendrá una arquitectura orientada a:

- componentes reutilizables;
- consumo centralizado de la API;
- diseño adaptable;
- experiencia móvil prioritaria;
- instalación como PWA;
- separación de lógica y presentación.

La estructura definitiva se documentará en:

```text
docs/architecture/Frontend.md
```

---

## 15. Manejo de configuración

Los datos sensibles y configurables no deberán escribirse directamente en el código.

Se utilizarán variables de entorno para valores como:

- credenciales;
- nombre de base de datos;
- puerto;
- secretos;
- URL de conexión.

El archivo `.env` no deberá subirse al repositorio.

El proyecto deberá incluir posteriormente un archivo de ejemplo:

```text
.env.example
```

Este archivo mostrará las variables necesarias sin contener valores privados.

---

## 16. Principios arquitectónicos

### Claridad

El código debe priorizar nombres claros y responsabilidades bien definidas.

### Consistencia

Los módulos deberán seguir las mismas convenciones.

### Escalabilidad

Las decisiones deberán permitir añadir nuevas funcionalidades sin rehacer el núcleo del sistema.

### Mantenibilidad

La lógica repetida deberá centralizarse cuando sea razonable.

### Modularidad

Cada módulo funcional deberá tener límites claros.

### Seguridad

Los permisos deben validarse en el backend y no depender únicamente del frontend.

### Simplicidad

No se añadirá complejidad sin una necesidad real.

---

## 17. Fuente de verdad

La documentación dentro de `docs/` será la fuente oficial de las decisiones del proyecto.

En caso de contradicción:

1. prevalece una decisión aprobada mediante ADR;
2. después prevalece la documentación técnica vigente;
3. después prevalece `ProjectContext.md`;
4. una conversación antigua no debe considerarse fuente definitiva.

---

## 18. Estado de implementación

### Implementado

- Alembic inicializado.
- Backend FastAPI en ejecución.
- Conexión con PostgreSQL.
- Estructura inicial del backend.
- Modelo User.
- Modelo Workspace.
- Modelo WorkspaceMember.
- SQLAlchemy configurado.

### En proceso

- BaseEntity.
- Convenciones de claves foráneas.
- Convenciones de relaciones.
- Documentación inicial.

### Pendiente

- API versionada.
- Autenticación.
- Autorización.
- CRUD de workspaces.
- Frontend.
- Módulo de tareas.
- Schemas.
- Services.