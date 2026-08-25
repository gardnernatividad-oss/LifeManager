import { useV2CatalogSelector } from "../../hooks/useV2CatalogSelector";
import type { CatalogSelectorKind } from "../../api/v2CatalogApi";

interface Props {
  workspaceId: string;
  kind: CatalogSelectorKind;
  label: "Categoría" | "Tarea" | "Actividad";
  value: string;
  onChange: (value: string) => void;
  currentId?: string;
  required?: boolean;
}

export function V2CatalogSelector({ workspaceId, kind, label, value, onChange, currentId, required }: Props) {
  const query = useV2CatalogSelector(workspaceId, kind, currentId);
  if (query.isPending) return <p role="status">Cargando opciones de {label.toLowerCase()}…</p>;
  if (query.isError) return <div role="alert"><span>No pudimos cargar las opciones.</span> <button type="button" onClick={() => void query.refetch()}>Reintentar</button></div>;
  if (query.data.length === 0) return <p>No hay opciones activas disponibles.</p>;
  return <label>{label}<select aria-label={label} required={required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">Selecciona una opción</option>{query.data.map((option) => <option key={option.id} value={option.id}>{option.name}{!option.is_active ? " (Inactiva)" : ""}</option>)}</select></label>;
}

export const CategorySelector = (props: Omit<Props, "kind" | "label">) => <V2CatalogSelector {...props} kind="categories" label="Categoría" />;
export const TaskCatalogSelector = (props: Omit<Props, "kind" | "label">) => <V2CatalogSelector {...props} kind="tasks" label="Tarea" />;
export const ActivityCatalogSelector = (props: Omit<Props, "kind" | "label">) => <V2CatalogSelector {...props} kind="activities" label="Actividad" />;
