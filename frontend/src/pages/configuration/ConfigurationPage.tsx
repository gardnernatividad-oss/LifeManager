import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { getProfile, listTimezones, updateAuthenticatedUser } from "../../api/authApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { AuthenticatedUser, ProfileRead, ProfileUpdatePayload } from "../../types/auth";
import { WorkspaceManagement } from "./WorkspaceManagement";
import { NotificationSettings } from "./NotificationSettings";
import { CalendarPrivacySettings } from "./CalendarPrivacySettings";
import { SecuritySettings } from "./SecuritySettings";
import { AboutSettings } from "./AboutSettings";

function ProfileForm({ profile, timezones, user, setAuthenticatedUser }: {
  profile: ProfileRead;
  timezones: string[];
  user: AuthenticatedUser | null;
  setAuthenticatedUser: (user: AuthenticatedUser) => void;
}) {
  const client = useQueryClient();
  const [firstName, setFirstName] = useState(profile.first_name);
  const [lastName, setLastName] = useState(profile.last_name);
  const [timezone, setTimezone] = useState(profile.timezone);
  const [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(null);
  const dirty = firstName.trim() !== profile.first_name || lastName.trim() !== profile.last_name || timezone !== profile.timezone;

  const save = useMutation({
    mutationFn: (payload: ProfileUpdatePayload) => updateAuthenticatedUser(payload),
    onSuccess: async (saved) => {
      if (user) setAuthenticatedUser({ ...user, ...saved });
      client.setQueryData(queryKeys.profile, saved);
      setFeedback({ error: false, text: "Configuración guardada." });
      await Promise.all([
        client.invalidateQueries({ queryKey: queryKeys.home }),
        client.invalidateQueries({ queryKey: queryKeys.review }),
        client.invalidateQueries({ queryKey: queryKeys.planningTasksRoot }),
        client.invalidateQueries({ queryKey: queryKeys.trackingTasksRoot }),
        client.invalidateQueries({ queryKey: queryKeys.planningPendingItemsRoot }),
        client.invalidateQueries({ queryKey: queryKeys.trackingPendingItemsRoot }),
        client.invalidateQueries({ queryKey: queryKeys.planningProjectsRoot }),
        client.invalidateQueries({ queryKey: queryKeys.trackingProjectsRoot }),
        client.invalidateQueries({ queryKey: queryKeys.pendingItemReportsRoot }),
        client.invalidateQueries({ queryKey: queryKeys.projectReportsRoot }),
      ]);
    },
    onError: (error) => {
      setFeedback({
        error: true,
        text: axios.isAxiosError(error) && error.response?.status === 422
          ? "Revisa los datos ingresados."
          : axios.isAxiosError(error) && error.response?.status === 409
            ? "El perfil cambió. Actualiza e intenta nuevamente."
            : "No pudimos guardar la configuración. Intenta nuevamente.",
      });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setFeedback(null);
    const cleanedFirstName = firstName.trim();
    const cleanedLastName = lastName.trim();
    if (!cleanedFirstName || !cleanedLastName || !timezone) {
      setFeedback({ error: true, text: "Completa nombre, apellido y zona horaria." });
      return;
    }
    save.mutate({ first_name: cleanedFirstName, last_name: cleanedLastName, timezone, lock_version: profile.lock_version });
  }

  return <>
    {feedback ? <p className={feedback.error ? "review-notice review-notice--error" : "review-notice review-notice--success"} role={feedback.error ? "alert" : "status"}>{feedback.text}</p> : null}
    <form className="configuration-form" onSubmit={submit} noValidate>
      <div className="configuration-name-grid">
        <div className="form-field"><label htmlFor="profile-first-name">Nombre</label><input id="profile-first-name" autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} /></div>
        <div className="form-field"><label htmlFor="profile-last-name">Apellido</label><input id="profile-last-name" autoComplete="family-name" value={lastName} onChange={(event) => setLastName(event.target.value)} /></div>
      </div>
      <div className="form-field"><label htmlFor="profile-email">Correo electrónico</label><input id="profile-email" type="email" value={profile.email} readOnly aria-readonly="true" /><small>El correo electrónico requiere un flujo de verificación separado y no se edita aquí.</small></div>
      <div className="form-field"><label htmlFor="profile-timezone">Zona horaria</label><select id="profile-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)}>{timezones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select></div>
      <p className="form-help">LifeManager se muestra en español, usa fechas dd/mm/yyyy y comienza la semana el lunes.</p>
      <button className="primary-button" type="submit" disabled={save.isPending || !dirty}>{save.isPending ? "Guardando…" : "Guardar cambios"}</button>
    </form>
  </>;
}

export function ConfigurationPage() {
  const { user, setAuthenticatedUser } = useAuth();
  const profile = useQuery({ queryKey: queryKeys.profile, queryFn: getProfile });
  const timezones = useQuery({ queryKey: queryKeys.timezones, queryFn: listTimezones });

  return <section className="configuration-page">
    <header><p className="eyebrow">Cuenta personal</p><h1>Configuración</h1><p>Administra tu perfil y las preferencias disponibles de LifeManager.</p></header>
    <section className="configuration-panel" aria-labelledby="profile-heading">
      <h2 id="profile-heading">Perfil</h2>
      {profile.isPending ? <p role="status">Cargando perfil…</p> : profile.isError ? <div role="alert"><p>No pudimos cargar tu perfil.</p><button type="button" onClick={() => void profile.refetch()}>Reintentar</button></div> : timezones.isPending ? <p role="status">Cargando zonas horarias…</p> : timezones.isError ? <div role="alert"><p>No pudimos cargar las zonas horarias.</p><button type="button" onClick={() => void timezones.refetch()}>Reintentar</button></div> : <ProfileForm key={profile.data.id} profile={profile.data} timezones={timezones.data} user={user} setAuthenticatedUser={setAuthenticatedUser} />}
    </section>
    <NotificationSettings />
    <CalendarPrivacySettings />
    <WorkspaceManagement />
    <SecuritySettings />
    <AboutSettings />
  </section>;
}
