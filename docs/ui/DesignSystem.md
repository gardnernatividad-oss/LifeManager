# Principios de interfaz de LifeManager V1

## Densidad y composición

- Interfaz compacta y densa en información.
- Tablas y listas antes que tarjetas sobredimensionadas.
- Desktop aprovecha el ancho horizontal; móvil apila o redistribuye sin crear espacios excesivos.
- Las métricas de Inicio no son clicables y no funcionan como navegación.

## Controles

- Dropdowns para estados, categorías, maestros y opciones acotadas.
- Inputs de fecha para rangos; evitar grupos grandes de botones o chips.
- Acciones discretas: lápiz para corrección, papelera para borrado y `>` para detalle.
- Guardar explícito en Revisión y Seguimiento por lote.
- Excepción: Revisión > Tareas muestra simultáneamente No realizado y Completado en cada fila.

## Accesibilidad

- Encabezados y tablas semánticos.
- Labels explícitos en filtros y formularios.
- Estado y validación comunicados con texto, no solo color.
- Foco visible y controles accesibles por teclado.
- Reflow móvil sin scroll horizontal innecesario.

## Idioma

La interfaz V1 es española y todos los archivos se guardan como UTF-8. Los términos del dominio siguen `docs/project/Glossary.md`.
