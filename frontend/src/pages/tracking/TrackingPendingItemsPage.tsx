import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getHomeSummary } from "../../api/homeApi";
import { listAllCategoryOptions } from "../../api/planningPendingItemApi";
import { queryKeys } from "../../api/queryKeys";
import { listTrackingPendingItems, saveTrackingPendingItems } from "../../api/trackingPendingItemApi";
import { useAuth } from "../../hooks/useAuth";
import type { PendingItemCompliance, PendingItemState, PendingItemTrackingUpdate, PlanningPendingItem, TrackingPendingItemListParams } from "../../types/planningPendingItem";
import { formatLocalTimestamp, formatShortCalendarDate } from "../../utils/localizedDate";

type EditableField = "is_active" | "progress" | "comment";
type DirtyRow = Omit<PendingItemTrackingUpdate, "id">;

const stateLabels: Record<PendingItemState, string> = { NO_INICIADO: "No iniciado", EN_PROCESO: "En proceso", FINALIZADO: "Finalizado" };
const complianceLabels: Record<PendingItemCompliance, string> = { EN_PLAZO: "En plazo", ATRASADO: "Atrasado", CON_ADELANTO: "Con adelanto", A_TIEMPO: "A tiempo", CON_RETRASO: "Con retraso" };
const conflictMessage = "Los Pendientes cambiaron desde la última carga. Actualizamos el registro; vuelve a intentarlo.";

function originalValue(item: PlanningPendingItem, field: EditableField): boolean | number | string | null { return item[field]; }
function detail(days: number | null): string { return days === null ? "—" : `${days} ${days === 1 ? "día" : "días"}`; }

export function TrackingPendingItemsPage() {
  const client = useQueryClient();
  const { user } = useAuth();
  const [params, setParams] = useState<TrackingPendingItemListParams>({ page: 1, page_size: 25, is_active: true, unfinished: true });
  const [dirty, setDirty] = useState<Record<string, DirtyRow>>({});
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const categories = useQuery({ queryKey: queryKeys.categoryOptions, queryFn: listAllCategoryOptions });
  const items = useQuery({ queryKey: queryKeys.trackingPendingItems(params), queryFn: () => listTrackingPendingItems(params) });
  const home = useQuery({ queryKey: queryKeys.home, queryFn: getHomeSummary });

  function change(item: PlanningPendingItem, field: EditableField, value: boolean | number | string | null) {
    setDirty((current) => {
      const row: DirtyRow = { ...(current[item.id] ?? { lock_version: item.lock_version }) };
      if (value === originalValue(item, field)) delete row[field]; else Object.assign(row, { [field]: value });
      const hasChange = Object.keys(row).some((key) => key !== "lock_version");
      if (!hasChange) { const next = { ...current }; delete next[item.id]; return next; }
      return { ...current, [item.id]: row };
    });
    setMessage(null);
  }

  async function refreshRelated() {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.trackingPendingItemsRoot }),
      client.invalidateQueries({ queryKey: queryKeys.planningPendingItemsRoot }),
      client.invalidateQueries({ queryKey: queryKeys.review }),
      client.invalidateQueries({ queryKey: queryKeys.home }),
      client.invalidateQueries({ queryKey: queryKeys.pendingItemReportsRoot })
    ]);
  }

  const save = useMutation({
    mutationFn: () => saveTrackingPendingItems(Object.entries(dirty).map(([id, row]) => ({ id, ...row }))),
    onSuccess: async (response) => { setDirty({}); setSavedAt(response.saved_at); setMessage({ error: false, text: "Seguimiento de Pendientes guardado." }); await refreshRelated(); },
    onError: async (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setDirty({}); setMessage({ error: true, text: conflictMessage });
        await client.invalidateQueries({ queryKey: queryKeys.trackingPendingItemsRoot });
      } else setMessage({ error: true, text: "No pudimos guardar el seguimiento. Tus cambios siguen pendientes para reintentar." });
    }
  });

  const categoryList = categories.data ?? [];
  const rows = items.data?.items ?? [];
  const invalidProgress = Object.values(dirty).some((row) => row.progress !== undefined && (!Number.isInteger(row.progress) || row.progress < 0 || row.progress > 100));
  const displayedSavedAt = savedAt ?? home.data?.pending_items_last_tracking_saved_at ?? null;

  return <section className="pending-tracking-page">
    <header><p className="eyebrow">Seguimiento</p><h1>Seguimiento · Pendientes</h1><p>Última actualización: {formatLocalTimestamp(displayedSavedAt, user?.timezone ?? "UTC")}</p></header>
    <section className="pending-tracking-panel" aria-labelledby="pending-tracking-register"><h2 id="pending-tracking-register">Registro de Pendientes</h2>
      {categories.isPending ? <p role="status">Cargando Categorías…</p> : categories.isError ? <div role="alert"><p>No pudimos cargar las Categorías.</p><button type="button" onClick={() => void categories.refetch()}>Reintentar</button></div> : <div className="pending-tracking-filters">
        <label>Vigencia<select value={params.is_active === undefined ? "" : String(params.is_active)} onChange={(event) => setParams({ ...params, page: 1, is_active: event.target.value === "" ? undefined : event.target.value === "true" })}><option value="">Todas</option><option value="true">Activos</option><option value="false">Inactivos</option></select></label>
        <label>Categoría<select value={params.category_id ?? ""} onChange={(event) => setParams({ ...params, page: 1, category_id: event.target.value || undefined })}><option value="">Todas</option>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label>Estado<select value={params.unfinished ? "unfinished" : params.state ?? ""} onChange={(event) => setParams({ ...params, page: 1, unfinished: event.target.value === "unfinished" ? true : undefined, state: event.target.value && event.target.value !== "unfinished" ? event.target.value as PendingItemState : undefined })}><option value="">Todos</option><option value="unfinished">No finalizados</option>{Object.entries(stateLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Cumplimiento<select value={params.compliance ?? ""} onChange={(event) => setParams({ ...params, page: 1, compliance: (event.target.value || undefined) as PendingItemCompliance | undefined })}><option value="">Todos</option>{Object.entries(complianceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Desde<input type="date" value={params.planned_from ?? ""} onChange={(event) => setParams({ ...params, page: 1, planned_from: event.target.value || undefined })} /></label>
        <label>Hasta<input type="date" value={params.planned_to ?? ""} onChange={(event) => setParams({ ...params, page: 1, planned_to: event.target.value || undefined })} /></label>
      </div>}
      {message ? <p className={message.error ? "review-notice review-notice--error" : "review-notice review-notice--success"} role={message.error ? "alert" : "status"}>{message.text}</p> : null}
      {invalidProgress ? <p className="review-notice review-notice--error" role="alert">El avance debe ser un número entero entre 0 y 100.</p> : null}
      {items.isPending ? <p role="status">Cargando Pendientes…</p> : items.isError ? <div role="alert"><p>No pudimos cargar los Pendientes.</p><button type="button" onClick={() => void items.refetch()}>Reintentar</button></div> : rows.length === 0 ? <p className="review-empty">No hay Pendientes para los filtros seleccionados.</p> : <div className="pending-tracking-table" role="table" aria-label="Registro de Pendientes de Seguimiento">
        <div className="pending-tracking-row pending-tracking-row--head" role="row"><span role="columnheader">Vigencia</span><span role="columnheader">Fecha planificada</span><span role="columnheader">Fecha de cumplimiento</span><span role="columnheader">Pendiente</span><span role="columnheader">Categoría</span><span role="columnheader">Avance</span><span role="columnheader">Estado</span><span role="columnheader">Cumplimiento</span><span role="columnheader">Detalle</span><span role="columnheader">Comentario</span></div>
        {rows.map((item) => { const row = dirty[item.id]; const active = row?.is_active ?? item.is_active; const progress = row?.progress ?? item.progress; const comment = row && "comment" in row ? row.comment ?? "" : item.comment ?? ""; return <div className="pending-tracking-row" role="row" key={item.id}>
          <span role="cell">{item.is_active ? <select aria-label={`Vigencia de ${item.name}`} value={active ? "true" : "false"} onChange={(event) => change(item, "is_active", event.target.value === "true")}><option value="true">Activo</option><option value="false">Inactivo</option></select> : <span>Inactivo</span>}</span>
          <span role="cell">{item.planned_date ? formatShortCalendarDate(item.planned_date) : "—"}</span><span role="cell">{item.completion_date ? formatShortCalendarDate(item.completion_date) : "—"}</span><strong role="cell">{item.name}</strong><span role="cell">{item.category.name}</span>
          <span role="cell"><input aria-label={`Avance de ${item.name}`} type="number" min="0" max="100" step="1" value={progress} onChange={(event) => change(item, "progress", Number(event.target.value))} /></span>
          <span role="cell">{stateLabels[item.state as PendingItemState]}</span><span role="cell">{item.compliance ? complianceLabels[item.compliance as PendingItemCompliance] : "—"}</span><span role="cell">{detail(item.detail_days)}</span>
          <span role="cell"><input aria-label={`Comentario de ${item.name}`} value={comment} onChange={(event) => change(item, "comment", event.target.value || null)} /></span>
        </div>; })}
      </div>}
      <div className="pending-tracking-save"><span>{Object.keys(dirty).length} con cambios</span><button className="primary-button" type="button" disabled={Object.keys(dirty).length === 0 || invalidProgress || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Guardando…" : "Guardar"}</button></div>
      {items.data ? <div className="planning-pagination"><span>Página {items.data.page} de {Math.max(1, items.data.total_pages)}</span><label>Por página<select value={params.page_size} onChange={(event) => setParams({ ...params, page: 1, page_size: Number(event.target.value) })}>{[25, 50, 100].map((size) => <option key={size}>{size}</option>)}</select></label><button type="button" disabled={params.page <= 1} onClick={() => setParams({ ...params, page: params.page - 1 })}>Anterior</button><button type="button" disabled={params.page >= items.data.total_pages} onClick={() => setParams({ ...params, page: params.page + 1 })}>Siguiente</button></div> : null}
    </section>
  </section>;
}
