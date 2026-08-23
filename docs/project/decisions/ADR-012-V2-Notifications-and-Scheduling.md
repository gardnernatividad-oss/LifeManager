# ADR-012: Notificaciones, scheduler y canales externos V2

## Estado

Aceptado para implementación futura. No implementado.

## Fecha

2026-08-22

## Contexto

V2 necesita campana, reminders, Web Push y correo con costo inicial S/0. El envío remoto no debe comprometer transacciones de dominio ni dispersarse entre services.

## Decisión

- Domain mutations crean Notification lógica mediante un service reutilizable dentro de la misma transacción.
- Notification es la frontera persistida/outbox lógica; Web Push se envía después del commit mediante NotificationDelivery.
- Cloudflare Worker Cron invoca endpoints internos idempotentes de Render con firma HMAC, timestamp y protección de replay. El Worker nunca accede a Neon.
- Jobs reclaman trabajo de forma atómica, usan dedup keys y retries con backoff; toleran cold starts y ventanas omitidas.
- PushSubscription soporta múltiples dispositivos y secretos cifrados; 404/410 desactiva endpoints.
- El service worker muestra payload mínimo y abre deep links internos allowlisted.
- Email usa una interfaz provider-neutral para verificación/recovery; tokens se generan en dominio, solo digest se persiste y el adapter entrega.

## Consecuencias

- Fallas de Push/email no revierten cambios confirmados de dominio.
- No se requiere WebSocket ni worker permanente para V2 S/0.
- Se deben proteger secretos VAPID/email/scheduler y probar idempotencia, privacidad y retries.
- Proveedor, librería y valores operativos concretos se eligen después sin cambiar estos límites.
