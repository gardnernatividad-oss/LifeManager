# ADR-001: Arquitectura general del proyecto

## Estado

Aceptado.

## Fecha

2026-07-20.

## Contexto

LifeManager necesita una arquitectura que permita comenzar con un sistema de gestión de tareas y evolucionar hacia una plataforma más amplia de productividad personal, familiar y colaborativa.

El proyecto debe soportar desde el inicio:

- múltiples usuarios;
- espacios personales y compartidos;
- roles y permisos;
- crecimiento por módulos;
- acceso desde navegador y dispositivos móviles;
- una base técnica mantenible;
- futuras funcionalidades como hábitos, metas, finanzas, calendario, notas y proyectos.

También se necesita una arquitectura adecuada para un desarrollo progresivo, sin introducir desde el inicio una complejidad operativa innecesaria.

## Decisión

LifeManager utilizará una arquitectura cliente-servidor compuesta por:

- un frontend desarrollado con Next.js, React y TypeScript;
- un backend desarrollado con FastAPI y Python;
- una API REST como medio principal de comunicación;
- PostgreSQL como base de datos relacional;
- SQLAlchemy 2.x como ORM;
- Alembic para la gestión de migraciones;
- Git y GitHub para control de versiones.

La aplicación se desarrollará inicialmente como una Progressive Web App.

La arquitectura será modular, pero permanecerá dentro de una aplicación unificada durante las primeras versiones.

No se utilizarán microservicios en la etapa inicial.

## Estructura general

```text
Usuario
   │
   ▼
Frontend
Next.js
   │
   │ API REST
   ▼
Backend
FastAPI
   │
   ▼
PostgreSQL
```

## Responsabilidades

### Frontend

Será responsable de:

- mostrar la interfaz;
- gestionar la navegación;
- administrar formularios;
- consumir la API;
- manejar el estado visual;
- adaptar la experiencia a dispositivos móviles;
- permitir la instalación como PWA.

### Backend

Será responsable de:

- autenticación;
- autorización;
- lógica de negocio;
- validación de datos;
- gestión de usuarios;
- gestión de workspaces;
- gestión de permisos;
- persistencia de datos;
- exposición de endpoints.

### Base de datos

Será responsable de:

- almacenar información persistente;
- proteger la integridad referencial;
- aplicar restricciones;
- conservar relaciones entre entidades;
- soportar transacciones.

## Arquitectura modular

El sistema se dividirá en módulos funcionales.

Ejemplos:

- autenticación;
- usuarios;
- workspaces;
- tareas;
- hábitos;
- metas;
- finanzas;
- calendario;
- notas;
- proyectos.

Cada módulo podrá tener:

- endpoints;
- modelos;
- schemas;
- services;
- reglas de negocio;
- documentación.

Los módulos compartirán componentes comunes como:

- configuración;
- acceso a base de datos;
- autenticación;
- autorización;
- usuarios;
- workspaces;
- notificaciones.

## Alternativas consideradas

### Aplicación monolítica sin separación por responsabilidades

Se consideró construir una única aplicación con rutas, lógica de negocio y acceso a datos mezclados.

Fue descartada porque dificultaría:

- mantener el código;
- realizar pruebas;
- reutilizar lógica;
- añadir módulos;
- dividir el trabajo en el futuro.

### Microservicios

Se consideró separar desde el inicio cada módulo en un servicio independiente.

Fue descartado porque añadiría complejidad innecesaria en:

- despliegue;
- comunicación entre servicios;
- autenticación;
- observabilidad;
- pruebas;
- mantenimiento;
- costos.

El tamaño actual del proyecto no justifica esa arquitectura.

### Aplicación móvil nativa

Se consideró desarrollar aplicaciones separadas para Android y iOS.

Fue descartado para la primera etapa porque:

- aumentaría el tiempo de desarrollo;
- exigiría mantener más de una base de código;
- requeriría procesos de publicación;
- dificultaría realizar cambios rápidos.

La PWA permitirá validar el producto antes de considerar aplicaciones nativas.

### Backend como servicio

Se consideró utilizar plataformas que proporcionan autenticación, base de datos y API automáticamente.

Fue descartado como arquitectura principal porque LifeManager tendrá lógica de negocio propia, relaciones complejas, permisos por workspace y necesidades futuras que requieren mayor control del backend.

## Consecuencias positivas

- Separación clara entre interfaz, lógica de negocio y datos.
- Posibilidad de cambiar el frontend sin rehacer el backend.
- Posibilidad de utilizar la misma API desde futuras aplicaciones.
- Desarrollo modular.
- Mejor mantenibilidad.
- Mayor control sobre seguridad y permisos.
- PostgreSQL ofrece relaciones, restricciones y transacciones robustas.
- FastAPI permite desarrollar una API tipada y documentada.
- La PWA permite llegar rápidamente a computadoras y móviles.
- La arquitectura puede crecer sin adoptar microservicios prematuramente.

## Consecuencias negativas

- Será necesario mantener dos aplicaciones principales: frontend y backend.
- La integración entre frontend y backend requerirá configuración.
- La autenticación y autorización deberán implementarse correctamente.
- El equipo deberá mantener documentación y convenciones comunes.
- La PWA puede tener limitaciones frente a una aplicación móvil nativa.
- La separación por capas puede parecer más lenta durante las primeras funcionalidades.

## Riesgos

- Añadir demasiadas capas sin una necesidad real.
- Diseñar módulos futuros antes de validar el núcleo.
- Introducir microservicios prematuramente.
- Permitir que la lógica de negocio termine dentro de los endpoints.
- Duplicar validaciones de manera inconsistente.
- No actualizar la documentación conforme cambie la arquitectura.

## Reglas derivadas

A partir de esta decisión:

1. Los endpoints no deberán contener lógica de negocio extensa.
2. La lógica de negocio deberá ubicarse principalmente en services.
3. Los modelos de SQLAlchemy no deberán utilizarse directamente como contratos de la API.
4. Los schemas de Pydantic se utilizarán para entrada y salida de datos.
5. Las modificaciones del esquema deberán realizarse mediante Alembic.
6. Los permisos deberán validarse en el backend.
7. Los módulos deberán permanecer desacoplados cuando sea razonable.
8. No se crearán microservicios sin una necesidad técnica demostrada.
9. La documentación deberá actualizarse cuando cambie una decisión arquitectónica importante.
10. Un cambio que contradiga este ADR deberá registrarse mediante un nuevo ADR.

## Documentos relacionados

- `docs/architecture/Architecture.md`
- `docs/database/Database.md`
- `docs/project/ProjectContext.md`
- `docs/project/Roadmap.md`

## Revisión futura

Esta decisión deberá revisarse si ocurre alguna de las siguientes situaciones:

- la aplicación necesita escalar componentes de forma independiente;
- aparecen integraciones que requieren una arquitectura diferente;
- se decide desarrollar aplicaciones móviles nativas;
- el monolito modular se vuelve difícil de desplegar o mantener;
- existen mediciones que justifiquen separar servicios;
- cambia significativamente el stack tecnológico.