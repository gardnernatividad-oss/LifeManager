import { useEffect, useState } from "react";

export interface ColumnOption {
  key: string;
  label: string;
  defaultVisible?: boolean;
}

export function useColumnPreferences(userId: string, view: string, columns: ColumnOption[]) {
  const storageKey = `lifemanager.columns.${userId}.${view}`;
  const defaults = columns.filter((column) => column.defaultVisible !== false).map((column) => column.key);
  const [visible, setVisible] = useState<string[]>(() => {
    try {
      const stored = JSON.parse(window.localStorage.getItem(storageKey) ?? "null");
      return Array.isArray(stored) ? stored.filter((key): key is string => columns.some((column) => column.key === key)) : defaults;
    } catch {
      return defaults;
    }
  });
  useEffect(() => window.localStorage.setItem(storageKey, JSON.stringify(visible)), [storageKey, visible]);
  return { visible, setVisible };
}

export function ColumnPreferences({ columns, visible, onChange }: {
  columns: ColumnOption[];
  visible: string[];
  onChange: (visible: string[]) => void;
}) {
  return <details className="column-preferences"><summary>Columnas</summary><fieldset><legend>Columnas visibles</legend>{columns.map((column) => <div key={column.key}><input aria-label={`Mostrar columna ${column.label}`} type="checkbox" checked={visible.includes(column.key)} onChange={(event) => onChange(event.target.checked ? [...visible, column.key] : visible.filter((key) => key !== column.key))} /><span aria-hidden="true">{column.label}</span></div>)}</fieldset></details>;
}
