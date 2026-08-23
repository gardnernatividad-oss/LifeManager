# Principios de interfaz de LifeManager

## Alcance

Estos principios aplican al objetivo V2 y conservan las convenciones útiles de V1. La interfaz es Spanish-first, muestra fechas `dd/mm/yyyy` y comienza la semana en lunes.

## Mobile-first y densidad

- Móvil vertical es un objetivo primario.
- Se priorizan filas/tarjetas compactas y campos esenciales.
- Avance se representa con barras cuando aporte claridad.
- La información secundaria se mueve a páginas internas de detalle.
- Desktop puede usar tablas más completas.
- Los filtros son compactos y no dominan la pantalla.

## Navegación y creación

- `>` abre detalle en el área blanca, con flecha de retorno.
- No se expande contenido complejo debajo de filas.
- `+ Nueva` abre normalmente un modal compacto para creación simple.
- Comparación de Calendario usa página interna separada.
- Campana/notificaciones usa overlay o panel.

## Controles

- Los estados y errores se comunican con texto, no solo color.
- Los controles deshabilitados mantienen legibilidad, se atenúan, suprimen hover/animación y conservan el cursor normal.
- No se utiliza cursor `not-allowed` como convención visual.
- Los selectores se reservan para opciones acotadas; no concatenan nombre y Categoría en el selector de Tarea/Actividad.

## Calendario

- Desktop abre semanal.
- Móvil abre diario.
- Comparación es diaria.
- Solo disponibilidad usa bloques neutrales sin repetir Libre/Ocupado.
- Mostrar detalles no altera nombres añadiendo `[Workspace]`.
