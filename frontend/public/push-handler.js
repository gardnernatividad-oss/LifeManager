const notificationDestinations = {
  DAILY_SUMMARY_REMINDER: "/inicio",
  DAILY_REVIEW_REMINDER: "/revision",
  PENDING_FOLLOW_UP_REMINDER: "/seguimiento/pendientes",
  PROJECT_FOLLOW_UP_REMINDER: "/seguimiento/proyectos",
  ACTIVITY_REMINDER: "/calendario"
};

self.addEventListener("push", (event) => {
  let type = "";
  try { type = event.data?.json()?.type ?? ""; } catch { type = ""; }
  if (!(type in notificationDestinations)) return;
  event.waitUntil(self.registration.showNotification("LifeManager", { body: "Tienes una actualización pendiente.", data: { type } }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destination = notificationDestinations[event.notification.data?.type] ?? "/inicio";
  event.waitUntil(self.clients.openWindow(destination));
});
