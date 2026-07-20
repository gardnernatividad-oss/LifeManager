# LifeManager

**Versión del proyecto:** v0.1.0

**Estado:** En desarrollo

---

# Objetivo

LifeManager es una Progressive Web App (PWA) diseñada para ayudar a personas, familias y equipos a organizar sus responsabilidades, hábitos, objetivos y proyectos desde una única plataforma.

El objetivo principal es convertirse en un sistema integral de gestión personal y colaborativa, priorizando simplicidad para el usuario y una arquitectura escalable para futuras funcionalidades.

---

# Visión

LifeManager no será únicamente un gestor de tareas.

La aplicación evolucionará hasta convertirse en un ecosistema de productividad personal compuesto por módulos independientes que compartirán usuarios, espacios de trabajo, permisos, notificaciones y paneles de información.

---

# Estado actual

## Sprint actual

Sprint 2

## Completado

- Repositorio GitHub creado.
- Backend FastAPI inicializado.
- PostgreSQL configurado.
- SQLAlchemy configurado.
- Alembic configurado.
- Modelo User implementado.
- Modelo Workspace implementado.
- Modelo WorkspaceMember implementado.
- Primera migración creada correctamente.

## En progreso

- Refactor BaseEntity.
- Definición de convenciones del proyecto.

## Próximo objetivo

Construir el núcleo colaborativo de la aplicación antes de comenzar con los módulos funcionales.

---

# Stack tecnológico

## Backend

- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic

## Base de datos

- PostgreSQL

## Frontend

- Next.js
- React
- TypeScript

## Control de versiones

- Git
- GitHub

---

# Arquitectura general

La arquitectura será modular.

Todos los módulos compartirán el mismo sistema de autenticación, usuarios, permisos, notificaciones y espacios de trabajo.

Los módulos deberán permanecer desacoplados entre sí siempre que sea posible.

---

# Entidades principales

Actualmente definidas:

- User
- Workspace
- WorkspaceMember

Próximas entidades previstas:

- Category
- TaskTemplate
- TaskOccurrence
- TaskResponse
- Notification

Posteriormente:

- Habit
- Goal
- Finance
- Calendar
- Notes
- Projects
- Documents

---

# Principios de diseño

- Arquitectura modular.
- Código limpio.
- Convenciones consistentes.
- UUID como clave primaria.
- Soft Delete cuando aplique.
- SQLAlchemy 2.x.
- Tipado estricto.
- Escalabilidad antes que rapidez.

---

# Convenciones

## Base de datos

- UUID como Primary Key.
- Nombres de tablas en plural.
- snake_case.
- Foreign Keys explícitas.

## Backend

- FastAPI.
- Services separados de la API.
- Schemas separados de Models.
- Lógica de negocio fuera de los endpoints.

## Frontend

- Componentes reutilizables.
- Separación entre UI y lógica.

---

# Flujo de desarrollo

Cada nueva funcionalidad seguirá el siguiente proceso:

1. Diseño.
2. Revisión.
3. Implementación.
4. Actualización de documentación.
5. Commit.
6. Revisión.

---

# Gestión del proyecto

Este documento es la fuente oficial del estado del proyecto.

Si existe una diferencia entre una conversación y este documento, prevalecerá siempre este documento.

Todas las decisiones importantes deberán reflejarse posteriormente mediante un ADR dentro de:

docs/project/decisions/

---

# Próxima revisión

Actualizar este documento al finalizar cada Sprint.