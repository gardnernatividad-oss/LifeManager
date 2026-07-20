# ADR-002: Uso de UUID como clave primaria

## Estado

Aceptado.

## Fecha

2026-07-20

---

# Contexto

LifeManager será una aplicación multiusuario con múltiples workspaces, relaciones complejas entre entidades y posibilidad de futuras integraciones.

Desde las primeras versiones se espera que el sistema pueda crecer sin requerir cambios estructurales importantes en las claves primarias.

Era necesario decidir entre utilizar identificadores enteros autoincrementales (`INTEGER`) o identificadores universales (`UUID`).

---

# Decisión

Todas las entidades principales utilizarán UUID como clave primaria.

Ejemplo:

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid.uuid4,
)
```

Esta decisión aplica inicialmente a:

- User
- Workspace
- WorkspaceMember

Y también a las futuras entidades del sistema.

---

# Motivación

Los UUID ofrecen varias ventajas para la arquitectura prevista de LifeManager.

## Escalabilidad

Los registros pueden generarse sin depender del estado de la base de datos.

Esto facilita futuras integraciones, sincronizaciones o arquitecturas distribuidas.

---

## Seguridad

Los identificadores dejan de ser fácilmente predecibles.

Por ejemplo:

```
/users/1
/users/2
/users/3
```

es mucho más sencillo de recorrer que:

```
/users/550e8400-e29b-41d4-a716-446655440000
```

Aunque esto no reemplaza la autorización, añade una capa adicional de protección.

---

## Integraciones futuras

Si en el futuro existen:

- aplicaciones móviles;
- sincronización offline;
- importaciones;
- exportaciones;
- APIs públicas;

los UUID reducen significativamente la posibilidad de conflictos entre identificadores.

---

## Consistencia

Todas las entidades seguirán la misma estrategia de identificación.

Esto evita mezclar distintos tipos de claves primarias dentro del proyecto.

---

# Alternativas consideradas

## INTEGER autoincremental

Ventajas:

- ocupa menos espacio;
- índices ligeramente más pequeños;
- consultas marginalmente más rápidas.

Desventajas:

- identificadores predecibles;
- dependencia del servidor para generar IDs;
- posibles conflictos en integraciones futuras.

Fue descartado porque la diferencia de rendimiento no compensa las ventajas arquitectónicas de UUID para este proyecto.

---

# Consecuencias

## Positivas

- Mayor seguridad frente a enumeración de recursos.
- Mejor preparación para crecimiento futuro.
- Identificadores únicos globalmente.
- Menor riesgo de conflictos entre registros.
- Arquitectura consistente.

## Negativas

- Mayor tamaño de almacenamiento.
- Índices ligeramente más grandes.
- URLs menos legibles para humanos.

Estas desventajas se consideran aceptables para el tamaño esperado del proyecto.

---

# Reglas derivadas

A partir de esta decisión:

1. Todas las entidades principales utilizarán UUID.
2. Las claves foráneas deberán utilizar el mismo tipo.
3. No se mezclarán UUID e INTEGER como claves primarias.
4. Los modelos utilizarán `UUID(as_uuid=True)`.
5. Los schemas utilizarán `uuid.UUID`.

---

# Documentos relacionados

- `docs/database/Database.md`
- `docs/architecture/Architecture.md`

---

# Revisión futura

Esta decisión solo deberá revisarse si aparece una limitación técnica importante que justifique abandonar UUID como estrategia principal de identificación.