import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  createV2Catalog,
  deleteV2Catalog,
  listV2Catalog,
  setV2CatalogActive,
  updateV2Catalog,
  type CatalogKind,
  type V2CatalogItem,
  type V2Category,
} from "../../api/v2CatalogApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import type { WorkspaceSummary } from "../../types/auth";

interface Props {
  kind: CatalogKind;
  label: "Categorías" | "Tareas" | "Actividades";
  singular: "Categoría" | "Tarea" | "Actividad";
}

function safeMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const code = (error.response?.data as { error?: { code?: string } } | undefined)?.error?.code;
    if (code === "CATALOG_NAME_CONFLICT") return "Ya existe un registro con ese nombre.";
    if (code === "CATALOG_VERSION_CONFLICT") return "El registro cambió. Actualiza e inténtalo nuevamente.";
    if (code === "CATEGORY_UNAVAILABLE") return "La categoría no está disponible.";
    if (code === "CATALOG_REFERENCED") return "El registro está en uso. Puedes desactivarlo, pero no eliminarlo.";
  }
  return "No pudimos guardar los cambios.";
}

interface WorkspaceProps extends Props { workspace: WorkspaceSummary; }

function WorkspaceCatalogPage({ kind, label, singular, workspace }: WorkspaceProps) {
  const client = useQueryClient();
  const workspaceId = workspace.id;
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<"" | "true" | "false">("");
  const [editing, setEditing] = useState<V2Category | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const isCategory = kind === "categories";
  const params = { active: active === "" ? undefined : active === "true", search: search || undefined };
  const query = useQuery({ queryKey: queryKeys.v2Catalog(workspaceId, kind, params), queryFn: () => listV2Catalog<V2Category>(workspaceId, kind, params), enabled: Boolean(workspaceId) });
  const categories = useQuery({ queryKey: queryKeys.v2Catalog(workspaceId, "categories", { active: true }), queryFn: () => listV2Catalog<V2Category>(workspaceId, "categories", { active: true }), enabled: Boolean(workspaceId) && !isCategory });
  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.v2CatalogRoot(workspaceId) }),
    client.invalidateQueries({ queryKey: queryKeys.v2CatalogSelectorRoot(workspaceId) }),
  ]);
  const create = useMutation({ mutationFn: () => createV2Catalog(workspaceId, kind, { name, ...(!isCategory ? { category_id: categoryId } : {}) }), onSuccess: async () => { setName(""); setCategoryId(""); setMessage(`${singular} guardada.`); await refresh(); }, onError: (error) => setMessage(safeMessage(error)) });
  const update = useMutation({ mutationFn: () => updateV2Catalog(workspaceId, kind, editing!.id, { name: editing!.name, ...(!isCategory ? { category_id: (editing as V2CatalogItem).category_id } : {}), lock_version: editing!.lock_version }), onSuccess: async () => { setEditing(null); setMessage(`${singular} actualizada.`); await refresh(); }, onError: async (error) => { setEditing(null); setMessage(safeMessage(error)); await refresh(); } });
  const lifecycle = useMutation({ mutationFn: (item: V2Category) => setV2CatalogActive(workspaceId, kind, item, !item.is_active), onSuccess: refresh, onError: async (error) => { setMessage(safeMessage(error)); await refresh(); } });
  const remove = useMutation({ mutationFn: (item: V2Category) => deleteV2Catalog(workspaceId, kind, item), onSuccess: async () => { setMessage(`${singular} eliminada.`); await refresh(); }, onError: async (error) => { setMessage(safeMessage(error)); await refresh(); } });

  function submit(event: FormEvent) { event.preventDefault(); if (name.trim() && (isCategory || categoryId)) create.mutate(); }

  return <section className="master-data-page"><header><p className="eyebrow">Tablas</p><h1>{label}</h1><p>Catálogo de {label.toLowerCase()} de {workspace.name}.</p></header><section className="master-data-panel"><h2>Crear {singular}</h2>{!isCategory && categories.isPending ? <p role="status">Cargando categorías…</p> : !isCategory && categories.isError ? <div role="alert">No pudimos cargar las categorías. <button type="button" onClick={() => void categories.refetch()}>Reintentar</button></div> : <form className="master-data-create" onSubmit={submit}><label>Nombre<input maxLength={isCategory ? 100 : 150} value={name} onChange={(event) => setName(event.target.value)} /></label>{!isCategory ? <label>Categoría<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Selecciona una categoría</option>{categories.data?.items.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label> : null}<button className="primary-button" disabled={!name.trim() || (!isCategory && !categoryId) || create.isPending}>Crear</button></form>}</section><section className="master-data-panel"><h2>Registro de {label}</h2><div className="catalog-filters"><label>Buscar<input value={search} onChange={(event) => setSearch(event.target.value)} /></label><label>Vigencia<select value={active} onChange={(event) => setActive(event.target.value as typeof active)}><option value="">Todas</option><option value="true">Activas</option><option value="false">Inactivas</option></select></label></div>{message ? <p role="status">{message}</p> : null}{query.isPending ? <p role="status">Cargando {label.toLowerCase()}…</p> : query.isError ? <div role="alert">No pudimos cargar el catálogo. <button type="button" onClick={() => void query.refetch()}>Reintentar</button></div> : query.data.items.length === 0 ? <p className="review-empty">No hay resultados.</p> : <div className="catalog-card-list">{query.data.items.map((item) => <article className="catalog-card" key={item.id}>{editing?.id === item.id ? <form onSubmit={(event) => { event.preventDefault(); update.mutate(); }}><label>Nombre<input aria-label={`Nombre de ${singular} ${item.name}`} value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} /></label>{!isCategory ? <><label>Categoría<select value={(editing as V2CatalogItem).category_id} onChange={(event) => setEditing({ ...editing, category_id: event.target.value } as V2CatalogItem)}>{categories.data?.items.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><small>Esta reclasificación también cambia la Categoría mostrada en el historial asociado.</small></> : null}<button>Guardar</button><button type="button" onClick={() => setEditing(null)}>Cancelar</button></form> : <><div><strong>{item.name}</strong>{!isCategory ? <span>{(item as V2CatalogItem).category_name}</span> : null}<small>{item.is_active ? "Activa" : "Inactiva"}</small></div><div className="master-data-actions"><button type="button" aria-label={`Editar ${singular} ${item.name}`} onClick={() => setEditing(item)}>Editar</button><button type="button" onClick={() => lifecycle.mutate(item)}>{item.is_active ? "Desactivar" : "Activar"}</button>{item.can_delete ? <button type="button" onClick={() => { if (window.confirm(`¿Eliminar ${singular} "${item.name}"?`)) remove.mutate(item); }}>Eliminar</button> : null}</div></>}</article>)}</div>}</section></section>;
}

export function V2CatalogPage(props: Props) {
  const { workspace } = useAuth();
  if (!workspace) return <p role="status">Selecciona un espacio de trabajo.</p>;
  return <WorkspaceCatalogPage key={workspace.id} {...props} workspace={workspace} />;
}
