# Roadmap de LifeManager

**Versión actual:** v0.1.0

---

# Objetivo

Este documento define la evolución prevista de LifeManager.

El roadmap sirve como guía general del proyecto y podrá modificarse conforme aparezcan nuevas necesidades o cambien las prioridades.

No representa fechas de entrega, sino el orden lógico de desarrollo.

---

# Filosofía

El desarrollo seguirá un enfoque incremental.

Cada versión deberá aportar valor real y dejar una base sólida para la siguiente.

Se priorizará:

- estabilidad;
- calidad;
- mantenibilidad;
- escalabilidad.

No se desarrollarán funcionalidades únicamente porque sean interesantes si todavía no aportan valor al núcleo del sistema.

---

# v0.1.0 — Núcleo del sistema

## Objetivo

Construir la infraestructura base sobre la que se apoyará toda la aplicación.

### Backend

- Configuración de FastAPI.
- Configuración de PostgreSQL.
- Configuración de SQLAlchemy.
- Configuración de Alembic.
- Arquitectura del proyecto.
- BaseEntity.
- Configuración inicial.

### Base de datos

- User.
- Workspace.
- WorkspaceMember.

### Documentación

- Arquitectura.
- Base de datos.
- Contexto del proyecto.
- Roadmap.
- ADR iniciales.

**Estado:** En progreso.

---

# v0.2.0 — Autenticación

## Objetivo

Permitir que los usuarios puedan crear cuentas e iniciar sesión.

### Funcionalidades

- Registro.
- Inicio de sesión.
- Cierre de sesión.
- Hash de contraseñas.
- JWT.
- Refresh Token.
- Verificación de correo (si aplica).
- Recuperación de contraseña.
- Perfil básico.

**Estado:** Pendiente.

---

# v0.3.0 — Workspaces

## Objetivo

Completar el sistema colaborativo.

### Funcionalidades

- Crear workspace.
- Editar workspace.
- Eliminar workspace.
- Invitar miembros.
- Aceptar invitaciones.
- Roles.
- Permisos.
- Cambio de propietario.

**Estado:** Pendiente.

---

# v0.4.0 — Gestión de tareas

## Objetivo

Implementar el primer módulo funcional de LifeManager.

### Entidades

- Category.
- TaskTemplate.
- TaskOccurrence.
- TaskResponse.

### Funcionalidades

- Crear tareas.
- Editar tareas.
- Eliminar tareas.
- Tareas recurrentes.
- Tareas únicas.
- Estados.
- Prioridades.
- Fechas límite.
- Comentarios.

**Estado:** Pendiente.

---

# v0.5.0 — Formularios diarios

## Objetivo

Implementar el sistema diario de cumplimiento.

### Funcionalidades

- Formulario diario.
- Registro de respuestas.
- Cumplido / No cumplido.
- Observaciones.
- Historial.
- Recordatorios.

**Estado:** Pendiente.

---

# v0.6.0 — Dashboard

## Objetivo

Visualizar el rendimiento de los usuarios.

### Funcionalidades

- Indicadores.
- Gráficos.
- Tendencias.
- Cumplimiento semanal.
- Cumplimiento mensual.
- Comparativas.
- Estadísticas.

**Estado:** Pendiente.

---

# v0.7.0 — Notificaciones

## Objetivo

Mantener informados a los usuarios.

### Funcionalidades

- Recordatorios.
- Push Notifications.
- Notificaciones internas.
- Configuración de notificaciones.
- Recordatorios automáticos.

**Estado:** Pendiente.

---

# v0.8.0 — Aplicación PWA completa

## Objetivo

Completar la experiencia móvil.

### Funcionalidades

- Instalación.
- Offline básico.
- Caché.
- Sincronización.
- Iconos.
- Splash Screen.

**Estado:** Pendiente.

---

# Módulos futuros

Cuando el núcleo esté consolidado podrán desarrollarse nuevos módulos.

## Hábitos

Seguimiento de hábitos personales.

## Metas

Objetivos a corto, mediano y largo plazo.

## Finanzas

Control financiero personal y familiar.

## Calendario

Agenda integrada.

## Notas

Sistema de notas rápidas.

## Documentos

Gestión documental.

## Proyectos

Seguimiento de proyectos complejos.

Estos módulos aún no tienen una planificación detallada.

---

# Criterios para avanzar de versión

Una versión solo podrá considerarse terminada cuando:

- la funcionalidad esté implementada;
- exista documentación actualizada;
- las migraciones estén revisadas;
- las pruebas principales sean satisfactorias;
- el código cumpla las convenciones del proyecto.

---

# Prioridad actual

Actualmente el proyecto está enfocado en:

1. Completar el núcleo colaborativo.
2. Finalizar la arquitectura.
3. Completar la documentación.
4. Implementar autenticación.
5. Construir el módulo de tareas.

---

# Estado general

| Versión | Estado |
|---------|--------|
| v0.1.0 | 🟡 En desarrollo |
| v0.2.0 | ⚪ Pendiente |
| v0.3.0 | ⚪ Pendiente |
| v0.4.0 | ⚪ Pendiente |
| v0.5.0 | ⚪ Pendiente |
| v0.6.0 | ⚪ Pendiente |
| v0.7.0 | ⚪ Pendiente |
| v0.8.0 | ⚪ Pendiente |

---

# Actualización del roadmap

Este documento deberá actualizarse únicamente cuando:

- cambie la prioridad del proyecto;
- se añada un módulo importante;
- una versión se complete;
- se modifique significativamente la estrategia de desarrollo.