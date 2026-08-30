import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { listTimezones, updateAuthenticatedUser } from "../../api/authApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { ProfileUpdatePayload } from "../../types/auth";
import { WorkspaceManagement } from "./WorkspaceManagement";
import { NotificationSettings } from "./NotificationSettings";

export function ConfigurationPage() {
  const { user, setAuthenticatedUser } = useAuth();
  const client = useQueryClient();
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [timezone, setTimezone] = useState(user?.timezone ?? "");
  const [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(null);
  const timezones = useQuery({ queryKey: queryKeys.timezones, queryFn: listTimezones });

  const save = useMutation({
    mutationFn: (payload: ProfileUpdatePayload) => updateAuthenticatedUser(payload),
    onSuccess: async (saved) => {
      setAuthenticatedUser(saved);
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
    save.mutate({ first_name: cleanedFirstName, last_name: cleanedLastName, timezone });
  }

  return <section className="configuration-page">
    <header><p className="eyebrow">Perfil</p><h1>Configuración</h1></header>
    <section className="configuration-panel" aria-labelledby="profile-heading">
      <h2 id="profile-heading">Perfil personal</h2>
      {feedback ? <p className={feedback.error ? "review-notice review-notice--error" : "review-notice review-notice--success"} role={feedback.error ? "alert" : "status"}>{feedback.text}</p> : null}
      <form className="configuration-form" onSubmit={submit} noValidate>
        <div className="configuration-name-grid">
          <div className="form-field"><label htmlFor="profile-first-name">Nombre</label><input id="profile-first-name" autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} /></div>
          <div className="form-field"><label htmlFor="profile-last-name">Apellido</label><input id="profile-last-name" autoComplete="family-name" value={lastName} onChange={(event) => setLastName(event.target.value)} /></div>
        </div>
        <div className="form-field"><label htmlFor="profile-email">Correo electrónico</label><input id="profile-email" type="email" value={user?.email ?? ""} readOnly aria-readonly="true" /><small>El correo electrónico no puede modificarse en V1.</small></div>
        <div className="form-field"><label htmlFor="profile-timezone">Zona horaria</label>{timezones.isPending ? <p role="status">Cargando zonas horarias…</p> : timezones.isError ? <div role="alert"><p>No pudimos cargar las zonas horarias.</p><button type="button" onClick={() => void timezones.refetch()}>Reintentar</button></div> : <select id="profile-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)}>{timezones.data.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select>}</div>
        <button className="primary-button" type="submit" disabled={save.isPending || !timezones.isSuccess}>{save.isPending ? "Guardando…" : "Guardar"}</button>
      </form>
    </section>
    <NotificationSettings />
    <WorkspaceManagement />
  </section>;
}
