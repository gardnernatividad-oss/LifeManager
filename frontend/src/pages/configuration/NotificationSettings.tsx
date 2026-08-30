import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { getNotificationPreferences, updateNotificationPreferences } from "../../api/v2NotificationApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { NotificationPreferences } from "../../types/v2Notifications";

const weekdays = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const permissionLabel = (value: NotificationPermission | "unsupported") => value === "granted" ? "Permitidas" : value === "denied" ? "Bloqueadas" : value === "default" ? "Aún no solicitadas" : "No compatibles";

export function NotificationSettings() {
  const query = useQuery({ queryKey: queryKeys.notificationPreferences, queryFn: getNotificationPreferences });
  if (query.isError) return <section className="configuration-panel" aria-labelledby="notifications-heading"><h2 id="notifications-heading">Notificaciones</h2><div role="alert"><p>No pudimos cargar las preferencias.</p><button type="button" onClick={() => void query.refetch()}>Reintentar</button></div></section>;
  if (query.isPending) return <section className="configuration-panel" aria-labelledby="notifications-heading"><h2 id="notifications-heading">Notificaciones</h2><p role="status">Cargando preferencias…</p></section>;
  return <NotificationSettingsForm initial={query.data} />;
}

function NotificationSettingsForm({ initial }: { initial: NotificationPreferences }) {
  const { user } = useAuth(); const client = useQueryClient();
  const [draft, setDraft] = useState<NotificationPreferences>(initial); const [message, setMessage] = useState<string | null>(null);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(() => typeof Notification === "undefined" ? "unsupported" : Notification.permission);
  const save = useMutation({ mutationFn: updateNotificationPreferences, onSuccess: async (saved) => { setDraft(saved); client.setQueryData(queryKeys.notificationPreferences, saved); setMessage("Preferencias de notificaciones guardadas."); await client.invalidateQueries({ queryKey: queryKeys.notificationPreferences }); }, onError: (error) => { setMessage(axios.isAxiosError(error) && error.response?.status === 409 ? "Las preferencias cambiaron. Recarga antes de guardar." : "No pudimos guardar las preferencias."); } });
  const update = (key: keyof NotificationPreferences, values: object) => setDraft((current) => ({ ...current, [key]: { ...current[key], ...values } }));
  const requestPermission = async () => { if (typeof Notification !== "undefined") setPermission(await Notification.requestPermission()); };
  const submit = (event: FormEvent) => { event.preventDefault(); setMessage(null); save.mutate(draft); };
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial);
  return <section className="configuration-panel" aria-labelledby="notifications-heading"><h2 id="notifications-heading">Notificaciones</h2><p>Los horarios usan tu zona horaria: <strong>{user?.timezone}</strong>.</p><form className="notification-settings" onSubmit={submit}>
    {([ ["daily_summary", "Resumen diario"], ["daily_review", "Revisión diaria"], ["pending_weekly", "Pendientes"], ["project_weekly", "Proyectos"] ] as const).map(([key, label]) => { const item = draft[key]; const weekly = key.endsWith("weekly"); return <fieldset key={key}><legend>{label}</legend><label><input type="checkbox" checked={item.enabled} onChange={(event) => update(key, { enabled: event.target.checked })} />Activar {label}</label>{weekly ? <label>Día<select value={item.weekday ?? 6} disabled={!item.enabled} onChange={(event) => update(key, { weekday: Number(event.target.value) })}>{weekdays.map((day, index) => <option value={index} key={day}>{day}</option>)}</select></label> : null}<label>Hora<input type="time" value={item.local_time.slice(0, 5)} disabled={!item.enabled} onChange={(event) => update(key, { local_time: `${event.target.value}:00` })} /></label></fieldset>; })}
    <fieldset><legend>Recordatorios de Actividades</legend><label><input type="checkbox" checked={draft.activity_reminders.enabled} onChange={(event) => update("activity_reminders", { enabled: event.target.checked })} />Activar recordatorios</label></fieldset>
    <div className="notification-permission"><span>Permiso del navegador: <strong>{permissionLabel(permission)}</strong></span>{permission === "default" ? <button type="button" onClick={() => void requestPermission()}>Permitir notificaciones</button> : null}</div>
    {message ? <p role="status">{message}</p> : null}<button className="primary-button" type="submit" disabled={save.isPending || !dirty}>{save.isPending ? "Guardando…" : "Guardar notificaciones"}</button>
  </form></section>;
}
