import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "../../api/queryKeys";
import { getCalendarVisibility, setCalendarVisibility } from "../../api/v2CalendarComparisonApi";
import { listManagedWorkspaces } from "../../api/workspaceApi";
import { useAuth } from "../../hooks/useAuth";
import type { WorkspaceSummary } from "../../types/auth";
import type { CalendarVisibility } from "../../types/v2CalendarComparison";

function PrivacySetting({ workspace }: { workspace: WorkspaceSummary }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const setting = useQuery({
    queryKey: queryKeys.calendarVisibility(user?.id ?? "anonymous", workspace.id),
    queryFn: () => getCalendarVisibility(workspace.id),
    enabled: Boolean(user),
  });
  const save = useMutation({
    mutationFn: (visibility: CalendarVisibility) => setCalendarVisibility(
      workspace.id,
      visibility,
      setting.data!.lock_version,
    ),
    onSuccess: (saved) => {
      client.setQueryData(queryKeys.calendarVisibility(user!.id, workspace.id), saved);
      client.removeQueries({ queryKey: queryKeys.calendarComparisonRoot(user!.id, workspace.id) });
    },
    onError: async () => {
      await setting.refetch();
    },
  });

  return <li className="calendar-privacy__item">
    <div><strong>{workspace.name}</strong><span>Espacio compartido</span></div>
    {setting.isPending ? <p role="status">Cargando privacidad…</p> : setting.isError ? <div role="alert"><p>No pudimos cargar esta preferencia.</p><button type="button" onClick={() => void setting.refetch()}>Reintentar</button></div> : <label>
      Compartir
      <select
        aria-label={`Privacidad de calendario en ${workspace.name}`}
        value={setting.data.visibility}
        disabled={save.isPending}
        onChange={(event) => save.mutate(event.target.value as CalendarVisibility)}
      >
        <option value="SHOW_DETAILS">Mostrar detalles</option>
        <option value="AVAILABILITY_ONLY">Solo disponibilidad</option>
        <option value="HIDE">Ocultar</option>
      </select>
    </label>}
    {save.isPending ? <p role="status">Guardando privacidad…</p> : save.isSuccess ? <p role="status">Privacidad guardada.</p> : save.isError ? <p role="alert">{axios.isAxiosError(save.error) && save.error.response?.status === 409 ? "La preferencia cambió. Se cargó su valor actual; intenta nuevamente." : "No pudimos guardar la privacidad. Intenta nuevamente."}</p> : null}
  </li>;
}

export function CalendarPrivacySettings() {
  const workspaces = useQuery({ queryKey: queryKeys.workspaceManagement, queryFn: listManagedWorkspaces });
  const shared = workspaces.data?.filter((workspace) => workspace.kind === "SHARED" && workspace.lifecycle === "ACTIVE") ?? [];

  return <section className="configuration-panel calendar-privacy" aria-labelledby="calendar-privacy-heading">
    <h2 id="calendar-privacy-heading">Privacidad de Calendario</h2>
    <p>Decide qué pueden ver de tu calendario consolidado los miembros de cada espacio compartido.</p>
    {workspaces.isPending ? <p role="status">Cargando espacios compartidos…</p> : workspaces.isError ? <div role="alert"><p>No pudimos cargar los espacios compartidos.</p><button type="button" onClick={() => void workspaces.refetch()}>Reintentar</button></div> : shared.length === 0 ? <p className="settings-empty">No perteneces a espacios compartidos activos.</p> : <ul className="calendar-privacy__list">{shared.map((workspace) => <PrivacySetting key={workspace.id} workspace={workspace} />)}</ul>}
  </section>;
}
