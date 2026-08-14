import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { createPlanningPendingItem, listAllCategoryOptions, listPlanningPendingItems, updatePlanningPendingItem } from "../../api/planningPendingItemApi";
import { queryKeys } from "../../api/queryKeys";
import type { PendingItemListParams, PendingItemUpdatePayload, PlanningPendingItem } from "../../types/planningPendingItem";
import { formatShortCalendarDate } from "../../utils/localizedDate";

interface FormState { categoryId: string; name: string; isActive: boolean; plannedDate: string }
const emptyForm: FormState = { categoryId: "", name: "", isActive: true, plannedDate: "" };
const conflictMessage = "El Pendiente cambió desde la última carga. Actualizamos el registro; vuelve a intentarlo.";

function valid(form: FormState): string | null {
  if (!form.categoryId || !form.name.trim()) return "Completa la Categoría y el nombre.";
  if (form.isActive && !form.plannedDate) return "Un Pendiente activo requiere fecha planificada.";
  return null;
}

export function PlanningPendingItemsPage() {
  const client = useQueryClient();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState<(FormState & { id: string; lockVersion: number }) | null>(null);
  const [params, setParams] = useState<PendingItemListParams>({ page: 1, page_size: 25 });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const categories = useQuery({ queryKey: queryKeys.categoryOptions, queryFn: listAllCategoryOptions });
  const items = useQuery({ queryKey: queryKeys.planningPendingItems(params), queryFn: () => listPlanningPendingItems(params) });

  async function refreshRelated() { await Promise.all([client.invalidateQueries({ queryKey: queryKeys.planningPendingItemsRoot }), client.invalidateQueries({ queryKey: queryKeys.home }), client.invalidateQueries({ queryKey: queryKeys.review }), client.invalidateQueries({ queryKey: queryKeys.pendingItemReportsRoot })]); }
  const create = useMutation({ mutationFn: () => createPlanningPendingItem({ category_id: form.categoryId, name: form.name.trim(), is_active: form.isActive, planned_date: form.isActive ? form.plannedDate : null }), onSuccess: async () => { setForm(emptyForm); setError(null); setNotice("Pendiente creado."); await refreshRelated(); }, onError: (caught) => { setNotice(null); setError(axios.isAxiosError(caught) && caught.response?.status === 409 ? "No se pudo crear porque la información relacionada cambió." : "No pudimos crear el Pendiente."); } });
  const update = useMutation({ mutationFn: (payload: PendingItemUpdatePayload) => updatePlanningPendingItem(editing!.id, payload), onSuccess: async () => { setEditing(null); setError(null); setNotice("Pendiente actualizado."); await refreshRelated(); }, onError: async (caught) => { setEditing(null); setNotice(null); setError(axios.isAxiosError(caught) && caught.response?.status === 409 ? conflictMessage : "No pudimos actualizar el Pendiente."); await client.invalidateQueries({ queryKey: queryKeys.planningPendingItemsRoot }); } });

  function submitCreate(event: FormEvent) { event.preventDefault(); const issue = valid(form); if (issue) return setError(issue); create.mutate(); }
  function beginEdit(item: PlanningPendingItem) { setEditing({ id: item.id, lockVersion: item.lock_version, categoryId: item.category_id, name: item.name, isActive: item.is_active, plannedDate: item.planned_date ?? "" }); setError(null); }
  function submitEdit(event: FormEvent) { event.preventDefault(); if (!editing) return; const issue = valid(editing); if (issue) return setError(issue); update.mutate({ category_id: editing.categoryId, name: editing.name.trim(), is_active: editing.isActive, planned_date: editing.isActive ? editing.plannedDate : null, lock_version: editing.lockVersion }); }
  const categoryList = categories.data ?? [];

  return <section className="pending-planning-page">
    <header><p className="eyebrow">Planificación</p><h1>Planificación · Pendientes</h1></header>
    <section className="pending-planning-panel" aria-labelledby="pending-create-title"><h2 id="pending-create-title">Crear Pendiente</h2>
      {categories.isPending ? <p role="status">Cargando Categorías…</p> : categories.isError ? <div role="alert"><p>No pudimos cargar las Categorías.</p><button className="secondary-button" type="button" onClick={() => void categories.refetch()}>Reintentar</button></div> : categoryList.length === 0 ? <p>Aún no hay Categorías configuradas en Tablas &gt; Categorías.</p> : <form className="pending-planning-form" onSubmit={submitCreate}>
        <label>Categoría<select required value={form.categoryId} onChange={(e) => setForm({ ...form, categoryId: e.target.value })}><option value="">Selecciona una Categoría</option>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label>Nombre<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>Vigencia<select value={form.isActive ? "active" : "inactive"} onChange={(e) => setForm({ ...form, isActive: e.target.value === "active", plannedDate: e.target.value === "active" ? form.plannedDate : "" })}><option value="active">Activo</option><option value="inactive">Inactivo</option></select></label>
        <label>Fecha planificada<input disabled={!form.isActive} required={form.isActive} type="date" value={form.plannedDate} onChange={(e) => setForm({ ...form, plannedDate: e.target.value })} /></label>
        <button className="primary-button" disabled={create.isPending} type="submit">{create.isPending ? "Creando…" : "Crear"}</button>
      </form>}
    </section>
    <section className="pending-planning-panel" aria-labelledby="pending-register-title"><h2 id="pending-register-title">Registro de Pendientes</h2>
      <div className="pending-planning-filters"><label>Vigencia<select value={params.is_active === undefined ? "" : String(params.is_active)} onChange={(e) => setParams({ ...params, page: 1, is_active: e.target.value === "" ? undefined : e.target.value === "true" })}><option value="">Todas</option><option value="true">Activos</option><option value="false">Inactivos</option></select></label><label>Categoría<select value={params.category_id ?? ""} onChange={(e) => setParams({ ...params, page: 1, category_id: e.target.value || undefined })}><option value="">Todas</option>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Desde<input type="date" value={params.planned_from ?? ""} onChange={(e) => setParams({ ...params, page: 1, planned_from: e.target.value || undefined })} /></label><label>Hasta<input type="date" value={params.planned_to ?? ""} onChange={(e) => setParams({ ...params, page: 1, planned_to: e.target.value || undefined })} /></label></div>
      {error ? <p className="review-notice review-notice--error" role="alert">{error}</p> : null}{notice ? <p className="review-notice review-notice--success" role="status">{notice}</p> : null}
      {items.isPending ? <div className="planning-loading" role="status">Cargando Pendientes…</div> : items.isError ? <div role="alert"><p>No pudimos cargar los Pendientes.</p><button className="secondary-button" type="button" onClick={() => void items.refetch()}>Reintentar</button></div> : items.data.items.length === 0 ? <p className="review-empty">No hay Pendientes para los filtros seleccionados.</p> : <div className="pending-planning-table" role="table" aria-label="Registro de Pendientes"><div className="pending-planning-row pending-planning-row--head" role="row"><span role="columnheader">Vigencia</span><span role="columnheader">Fecha planificada</span><span role="columnheader">Pendiente</span><span role="columnheader">Categoría</span><span role="columnheader">Acciones</span></div>{items.data.items.map((item) => <div className="pending-planning-row" role="row" key={item.id}>{editing?.id === item.id ? <form className="pending-planning-edit" onSubmit={submitEdit}><label><span className="sr-only">Vigencia de {item.name}</span><select aria-label={`Vigencia de ${item.name}`} value={editing.isActive ? "active" : "inactive"} onChange={(e) => setEditing({ ...editing, isActive: e.target.value === "active", plannedDate: e.target.value === "active" ? editing.plannedDate : "" })}><option value="active">Activo</option><option value="inactive">Inactivo</option></select></label><label><span className="sr-only">Fecha planificada de {item.name}</span><input aria-label={`Fecha planificada de ${item.name}`} disabled={!editing.isActive} required={editing.isActive} type="date" value={editing.plannedDate} onChange={(e) => setEditing({ ...editing, plannedDate: e.target.value })} /></label><label><span className="sr-only">Nombre de {item.name}</span><input aria-label={`Nombre de ${item.name}`} required value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></label><label><span className="sr-only">Categoría de {item.name}</span><select aria-label={`Categoría de ${item.name}`} value={editing.categoryId} onChange={(e) => setEditing({ ...editing, categoryId: e.target.value })}>{categoryList.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><span className="pending-planning-actions"><button aria-label={`Guardar ${item.name}`} type="submit">✓</button><button aria-label={`Cancelar edición de ${item.name}`} type="button" onClick={() => setEditing(null)}>×</button></span></form> : <><span role="cell">{item.is_active ? "Activo" : "Inactivo"}</span><span role="cell">{item.planned_date ? formatShortCalendarDate(item.planned_date) : "—"}</span><strong role="cell">{item.name}</strong><span role="cell">{item.category.name}</span><span role="cell" className="pending-planning-actions"><button aria-label={`Editar ${item.name}`} type="button" onClick={() => beginEdit(item)}>✎</button></span></>}</div>)}</div>}
      {items.data ? <div className="planning-pagination"><span>Página {items.data.page} de {Math.max(1, items.data.total_pages)}</span><label>Por página<select value={params.page_size} onChange={(e) => setParams({ ...params, page: 1, page_size: Number(e.target.value) })}>{[25,50,100].map((size) => <option key={size}>{size}</option>)}</select></label><button disabled={params.page <= 1} type="button" onClick={() => setParams({ ...params, page: params.page - 1 })}>Anterior</button><button disabled={params.page >= items.data.total_pages} type="button" onClick={() => setParams({ ...params, page: params.page + 1 })}>Siguiente</button></div> : null}
    </section>
  </section>;
}
