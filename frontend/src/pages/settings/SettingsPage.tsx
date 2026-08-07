import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { queryKeys } from "../../api/queryKeys";
import { getUserSettings, updateUserSettings } from "../../api/userSettingsApi";
import { getWorkspaceSettings, updateWorkspaceSettings } from "../../api/workspaceSettingsApi";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { UserSettings, UserSettingsWrite, WorkspaceSettings, WorkspaceSettingsWrite } from "../../types/settings";

const timePattern = /^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/;
const userSchema = z.object({
  timezone: z.string().trim().min(1, "Ingresa una zona horaria."),
  locale: z.string().trim().min(1, "Ingresa una configuración regional.").max(20, "Máximo 20 caracteres."),
  week_starts_on: z.enum(["MONDAY", "SUNDAY"]),
  daily_form_reminders_enabled: z.boolean(), task_due_reminders_enabled: z.boolean(), task_overdue_reminders_enabled: z.boolean(),
  daily_form_reminder_time: z.string().regex(timePattern, "Ingresa una hora válida."),
  task_due_reminder_minutes: z.number().int("Usa minutos enteros.").min(0, "El mínimo es 0.").max(1440, "El máximo es 1440.")
});
const workspaceSchema = z.object({
  timezone: z.string().trim().min(1, "Ingresa una zona horaria."), daily_form_enabled: z.boolean(),
  daily_form_reminder_time: z.string().regex(timePattern, "Ingresa una hora válida."),
  daily_task_generation_enabled: z.boolean(), week_starts_on: z.enum(["MONDAY", "SUNDAY"])
});

function messageFor(error: unknown, resource: string) {
  if (axios.isAxiosError(error) && error.response?.status === 403) return `No tienes permisos para modificar ${resource}.`;
  if (axios.isAxiosError(error) && error.response?.status === 422) return `No pudimos guardar ${resource}. Revisa los valores.`;
  return `No pudimos guardar ${resource}. Verifica la conexión e intenta nuevamente.`;
}

function UserSettingsForm({ settings }: { settings: UserSettings }) {
  const queryClient = useQueryClient(); const [notice, setNotice] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, reset, formState: { errors } } = useForm<UserSettingsWrite>({ resolver: zodResolver(userSchema), defaultValues: {
    timezone: settings.timezone, locale: settings.locale, week_starts_on: settings.week_starts_on,
    daily_form_reminders_enabled: settings.daily_form_reminders_enabled, task_due_reminders_enabled: settings.task_due_reminders_enabled,
    task_overdue_reminders_enabled: settings.task_overdue_reminders_enabled, daily_form_reminder_time: settings.daily_form_reminder_time.slice(0, 5),
    task_due_reminder_minutes: settings.task_due_reminder_minutes
  }});
  const mutation = useMutation({ mutationFn: updateUserSettings, onSuccess: (saved) => { queryClient.setQueryData(queryKeys.userSettings, saved); reset({ ...saved, daily_form_reminder_time: saved.daily_form_reminder_time.slice(0, 5) }); setError(null); setNotice("Preferencias guardadas."); }, onError: (caught) => { setNotice(null); setError(messageFor(caught, "las preferencias")); } });
  return <form className="settings-form" onSubmit={handleSubmit((values) => mutation.mutate({ ...values, timezone: values.timezone.trim(), locale: values.locale.trim() }))} noValidate>
    <div className="settings-field-grid"><div className="form-field"><label htmlFor="user-timezone">Zona horaria</label><input id="user-timezone" placeholder="America/Lima" {...register("timezone")} />{errors.timezone && <span className="field-error">{errors.timezone.message}</span>}<small>Usa un identificador IANA.</small></div><div className="form-field"><label htmlFor="user-locale">Configuración regional</label><input id="user-locale" {...register("locale")} />{errors.locale && <span className="field-error">{errors.locale.message}</span>}<small>Se almacena para uso futuro; la interfaz continúa en español.</small></div><div className="form-field"><label htmlFor="user-week-start">Primer día de la semana</label><select id="user-week-start" {...register("week_starts_on")}><option value="MONDAY">Lunes</option><option value="SUNDAY">Domingo</option></select></div><div className="form-field"><label htmlFor="user-reminder-time">Hora del recordatorio diario</label><input id="user-reminder-time" type="time" {...register("daily_form_reminder_time")} />{errors.daily_form_reminder_time && <span className="field-error">{errors.daily_form_reminder_time.message}</span>}</div><div className="form-field"><label htmlFor="task-reminder-minutes">Anticipación de tareas (minutos)</label><input id="task-reminder-minutes" type="number" min="0" max="1440" {...register("task_due_reminder_minutes", { valueAsNumber: true })} />{errors.task_due_reminder_minutes && <span className="field-error">{errors.task_due_reminder_minutes.message}</span>}</div></div>
    <fieldset className="settings-toggles"><legend>Recordatorios</legend><label><input type="checkbox" {...register("daily_form_reminders_enabled")} />Formulario diario</label><label><input type="checkbox" {...register("task_due_reminders_enabled")} />Tareas próximas</label><label><input type="checkbox" {...register("task_overdue_reminders_enabled")} />Tareas vencidas</label></fieldset>
    {notice && <div className="success-notice" role="status">{notice}</div>}{error && <div className="form-alert" role="alert">{error}</div>}<button className="primary-button" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Guardando…" : "Guardar preferencias"}</button>
  </form>;
}

function WorkspaceSettingsForm({ settings, workspaceName }: { settings: WorkspaceSettings; workspaceName: string }) {
  const queryClient = useQueryClient(); const [notice, setNotice] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);
  const { register, control, handleSubmit, reset, formState: { errors } } = useForm<WorkspaceSettingsWrite>({ resolver: zodResolver(workspaceSchema), defaultValues: { timezone: settings.timezone, daily_form_enabled: settings.daily_form_enabled, daily_form_reminder_time: settings.daily_form_reminder_time.slice(0, 5), daily_task_generation_enabled: settings.daily_task_generation_enabled, week_starts_on: settings.week_starts_on } });
  const formEnabled = useWatch({ control, name: "daily_form_enabled" }); const generationEnabled = useWatch({ control, name: "daily_task_generation_enabled" });
  const mutation = useMutation({ mutationFn: (payload: WorkspaceSettingsWrite) => updateWorkspaceSettings(settings.workspace_id, payload), onSuccess: (saved) => { queryClient.setQueryData(queryKeys.workspaceSettings(settings.workspace_id), saved); reset({ ...saved, daily_form_reminder_time: saved.daily_form_reminder_time.slice(0, 5) }); setError(null); setNotice("Configuración del espacio actualizada."); }, onError: (caught) => { setNotice(null); setError(messageFor(caught, "la configuración del espacio")); } });
  return <form className="settings-form" onSubmit={handleSubmit((values) => mutation.mutate({ ...values, timezone: values.timezone.trim() }))} noValidate><fieldset className="settings-readonly-fieldset" disabled={mutation.isPending}><legend className="sr-only">Configuración de {workspaceName}</legend><div className="settings-field-grid"><div className="form-field"><label htmlFor="workspace-timezone">Zona horaria del espacio</label><input id="workspace-timezone" placeholder="America/Lima" {...register("timezone")} />{errors.timezone && <span className="field-error">{errors.timezone.message}</span>}<small>Esta zona controla el comportamiento operativo configurado para el espacio.</small></div><div className="form-field"><label htmlFor="workspace-week-start">Primer día de la semana</label><select id="workspace-week-start" {...register("week_starts_on")}><option value="MONDAY">Lunes</option><option value="SUNDAY">Domingo</option></select></div><div className="form-field"><label htmlFor="workspace-reminder-time">Hora del formulario diario</label><input id="workspace-reminder-time" type="time" aria-describedby={!formEnabled ? "form-time-disabled-note" : undefined} {...register("daily_form_reminder_time")} />{errors.daily_form_reminder_time && <span className="field-error">{errors.daily_form_reminder_time.message}</span>}{!formEnabled && <small id="form-time-disabled-note">La hora se conserva, pero no se usa mientras el formulario esté desactivado.</small>}</div></div><div className="settings-toggles"><label><input type="checkbox" {...register("daily_form_enabled")} />Habilitar Formulario diario</label><label><input type="checkbox" {...register("daily_task_generation_enabled")} />Habilitar generación diaria de tareas</label></div>{!generationEnabled && <p className="settings-helper">El Seguimiento diario no generará tareas recurrentes para este espacio.</p>}</fieldset>
    {notice && <div className="success-notice" role="status">{notice}</div>}{error && <div className="form-alert" role="alert">{error}</div>}<button className="primary-button" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Guardando…" : "Guardar configuración del espacio"}</button>
  </form>;
}

export function SettingsPage() {
  const { user, workspace } = useAuth(); const workspaces = useWorkspaces(); const workspaceId = workspace?.id ?? "";
  const userQuery = useQuery({ queryKey: queryKeys.userSettings, queryFn: getUserSettings });
  const workspaceQuery = useQuery({ queryKey: queryKeys.workspaceSettings(workspaceId), queryFn: () => getWorkspaceSettings(workspaceId), enabled: !!workspaceId });
  return <div className="settings-page"><header className="settings-header"><p className="eyebrow">{user?.email}</p><h1>Configuración</h1><p>Administra tus preferencias personales y el comportamiento del espacio seleccionado.</p></header>
    <section className="settings-panel" aria-labelledby="personal-settings-title"><h2 id="personal-settings-title">Preferencias personales</h2><p>Estas preferencias pertenecen a tu usuario y son independientes del espacio seleccionado.</p>{userQuery.isPending && <div className="settings-skeleton" role="status">Cargando preferencias…</div>}{userQuery.isError && <div className="dashboard-error" role="alert"><p>No pudimos cargar tus preferencias.</p><button className="secondary-button" onClick={() => void userQuery.refetch()}>Reintentar</button></div>}{userQuery.data && <UserSettingsForm key={userQuery.data.id} settings={userQuery.data} />}</section>
    <section className="settings-panel" aria-labelledby="workspace-settings-title"><h2 id="workspace-settings-title">Configuración del espacio</h2><p>{workspace ? `Estos valores afectan el funcionamiento de ${workspace.name}.` : "Selecciona un espacio para consultar su configuración."}</p>{workspaces.isPending && <div className="settings-skeleton" role="status">Cargando espacios…</div>}{!workspaces.isPending && !workspace && <div className="settings-empty">No hay un espacio de trabajo seleccionado.</div>}{workspaceQuery.isPending && workspace && <div className="settings-skeleton" role="status">Cargando configuración del espacio…</div>}{workspaceQuery.isError && <div className="dashboard-error" role="alert"><p>No pudimos cargar la configuración del espacio.</p><button className="secondary-button" onClick={() => void workspaceQuery.refetch()}>Reintentar</button></div>}{workspaceQuery.data && workspace && <WorkspaceSettingsForm key={`${workspace.id}-${workspaceQuery.data.id}`} settings={workspaceQuery.data} workspaceName={workspace.name} />}</section>
  </div>;
}
