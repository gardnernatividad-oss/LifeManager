# Migraciones de LifeManager

## Baseline vigente

La cadena Alembic actual es lineal y tiene un solo head: `d3e4f5a6b7c8`. Las revisiones existentes son historial inmutable y no deben editarse.

El diseño V2 todavía no está implementado. La transición aprobada será una revisión nueva con parent `d3e4f5a6b7c8`, mediante reset destructivo controlado de datos V1 descartables. El límite, las salvaguardas, el orden de implementación y las pruebas obligatorias están definidos en [V2-Transition-Implementation-Plan.md](V2-Transition-Implementation-Plan.md).

## Reglas para la transición V2

- no ejecutar el reset sin opt-in explícito y validación local/test;
- no usar `DROP SCHEMA`, wildcards ni `DROP ... CASCADE`;
- no conectar pruebas destructivas a producción;
- verificar revisión y forma exacta del esquema antes del primer DROP;
- preservar `alembic_version` y todo objeto fuera de la allowlist;
- considerar irreversible el downgrade del reset;
- después del primer uso real V2, volver a migraciones preservadoras de datos.

Este documento y el plan son documentación; no autorizan crear o ejecutar la migración.
