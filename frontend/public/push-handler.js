const notificationDestinations = {
  DAILY_SUMMARY_REMINDER: "/inicio",
  DAILY_REVIEW_REMINDER: "/revision",
  PENDING_FOLLOW_UP_REMINDER: "/seguimiento/pendientes",
  PROJECT_FOLLOW_UP_REMINDER: "/seguimiento/proyectos",
  ACTIVITY_REMINDER: "/calendario"
};

self.addEventListener("push", (event) => {
  let payload = {};
  try { payload = event.data?.json() ?? {}; } catch { payload = {}; }
  const type = typeof payload.type === "string" ? payload.type : "";
  if (!(type in notificationDestinations)) return;
  const title = typeof payload.title === "string" ? payload.title.slice(0, 160) : "LifeManager";
  const body = typeof payload.body === "string" ? payload.body.slice(0, 500) : "Tienes una actualización pendiente.";
  event.waitUntil(self.registration.showNotification(title, { body, data: { type } }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destination = notificationDestinations[event.notification.data?.type] ?? "/inicio";
  event.waitUntil(self.clients.openWindow(destination));
});
