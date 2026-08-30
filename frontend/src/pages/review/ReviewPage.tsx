import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { queryKeys } from "../../api/queryKeys";
import { getReview, saveReviewPendingItems, saveReviewProjectStages, saveReviewTasks } from "../../api/reviewApi";
import type { ReviewPendingItem, ReviewProjectStage, ReviewTaskResult } from "../../types/review";
import { formatCalendarDate, formatShortCalendarDate } from "../../utils/localizedDate";

interface LocalEdit { progress: string; comment: string }
type EditMap = Record<string, LocalEdit>;
type Feedback = { error: boolean; text: string } | null;

const editFor = (row: ReviewPendingItem | ReviewProjectStage, edits: EditMap): LocalEdit =>
  edits[row.id] ?? { progress: String(row.progress), comment: "" };

function changedPendingEdit(row: ReviewPendingItem, edit: LocalEdit) {
  const progress = Number(edit.progress);
  return {
    ...(progress === row.progress ? {} : { progress }),
    ...(edit.comment.trim() ? { comment: edit.comment.trim() } : {}),
  };
}

function changedStageEdit(row: ReviewProjectStage, edit: LocalEdit) {
  return {
    ...(Number(edit.progress) === Number(row.progress) ? {} : { progress: edit.progress }),
    ...(edit.comment.trim() ? { comment: edit.comment.trim() } : {}),
  };
}

function validProgress(edits: LocalEdit[], decimal = false): boolean {
  return edits.every((edit) => {
    const value = Number(edit.progress);
    return Number.isFinite(value) && value >= 0 && value <= 100 && (decimal ? /^\d{1,3}(\.\d{1,2})?$/.test(edit.progress) : Number.isInteger(value));
  });
}

function FeedbackMessage({ feedback }: { feedback: Feedback }) {
  return feedback ? (
    <p className={feedback.error ? "review-notice review-notice--error" : "review-notice review-notice--success"} role={feedback.error ? "alert" : "status"}>
      {feedback.text}
    </p>
  ) : null;
}

function EditableRow({ row, edit, label, onChange }: {
  row: ReviewPendingItem | ReviewProjectStage;
  edit: LocalEdit;
  label: string;
  onChange: (edit: LocalEdit) => void;
}) {
  const name = "stage_name" in row ? row.stage_name : row.pending_item_name;
  return (
    <article className={`review-data-row review-data-row--v2 review-data-row--${"stage_name" in row ? "v2-stage" : "v2-pending"}`}>
      <span data-label="Fecha">{formatShortCalendarDate(row.planned_date)}</span>
      <span data-label="Workspace">{row.workspace_name}</span>
      {"stage_name" in row ? <span data-label="Proyecto">{row.project_name}</span> : null}
      <strong data-label={label}>{name}</strong>
      <label>
        <span>Avance de {name}</span>
        <input aria-label={`Avance de ${name}`} inputMode="decimal" min="0" max="100" step="0.01" type="number" value={edit.progress} onChange={(event) => onChange({ ...edit, progress: event.target.value })} />
      </label>
      <label>
        <span>Comentario de {name}</span>
        <input aria-label={`Comentario de ${name}`} maxLength={2000} value={edit.comment} onChange={(event) => onChange({ ...edit, comment: event.target.value })} />
      </label>
    </article>
  );
}

export function ReviewPage() {
  const client = useQueryClient();
  const review = useQuery({ queryKey: queryKeys.review, queryFn: getReview });
  const [taskResults, setTaskResults] = useState<Record<string, ReviewTaskResult>>({});
  const [pendingEdits, setPendingEdits] = useState<EditMap>({});
  const [stageEdits, setStageEdits] = useState<EditMap>({});
  const [taskFeedback, setTaskFeedback] = useState<Feedback>(null);
  const [pendingFeedback, setPendingFeedback] = useState<Feedback>(null);
  const [stageFeedback, setStageFeedback] = useState<Feedback>(null);

  async function refreshReviewAnd(keys: readonly (readonly unknown[])[]) {
    await Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })));
    await review.refetch();
  }

  const taskSave = useMutation({
    mutationFn: saveReviewTasks,
    onSuccess: async () => {
      const workspaceIds = new Set((review.data?.tasks ?? []).filter((row) => taskResults[row.id]).map((row) => row.workspace_id));
      setTaskResults({});
      setTaskFeedback({ error: false, text: "Tareas guardadas." });
      await refreshReviewAnd([queryKeys.home, queryKeys.taskReportsRoot, ...[...workspaceIds].map(queryKeys.v2TasksRoot)]);
    },
    onError: async (error) => {
      const stale = axios.isAxiosError(error) && error.response?.status === 409;
      if (stale) await review.refetch();
      setTaskFeedback({ error: true, text: stale ? "Las Tareas cambiaron. Actualizamos los datos y conservamos tus selecciones para que puedas revisarlas." : "No pudimos guardar las Tareas. Tus selecciones siguen disponibles." });
    },
  });
  const pendingSave = useMutation({
    mutationFn: saveReviewPendingItems,
    onSuccess: async () => {
      const workspaceIds = new Set((review.data?.pending_items ?? []).filter((row) => pendingEdits[row.id]).map((row) => row.workspace_id));
      setPendingEdits({});
      setPendingFeedback({ error: false, text: "Pendientes guardados." });
      await refreshReviewAnd([queryKeys.home, queryKeys.pendingItemReportsRoot, ...[...workspaceIds].map(queryKeys.v2PendingItemsRoot)]);
    },
    onError: async (error) => {
      const stale = axios.isAxiosError(error) && error.response?.status === 409;
      if (stale) await review.refetch();
      setPendingFeedback({ error: true, text: stale ? "Los Pendientes cambiaron. Actualizamos los datos y conservamos tus cambios para que puedas revisarlos." : "No pudimos guardar los Pendientes. Tus cambios siguen disponibles." });
    },
  });
  const stageSave = useMutation({
    mutationFn: saveReviewProjectStages,
    onSuccess: async () => {
      const workspaceIds = new Set((review.data?.project_stages ?? []).filter((row) => stageEdits[row.id]).map((row) => row.workspace_id));
      setStageEdits({});
      setStageFeedback({ error: false, text: "Proyectos guardados." });
      await refreshReviewAnd([queryKeys.home, queryKeys.projectReportsRoot, ...[...workspaceIds].map(queryKeys.v2ProjectsRoot)]);
    },
    onError: async (error) => {
      const stale = axios.isAxiosError(error) && error.response?.status === 409;
      if (stale) await review.refetch();
      setStageFeedback({ error: true, text: stale ? "Las Etapas cambiaron. Actualizamos los datos y conservamos tus cambios para que puedas revisarlos." : "No pudimos guardar los Proyectos. Tus cambios siguen disponibles." });
    },
  });

  if (review.isPending) return <section className="review-page" aria-label="Revisión"><p role="status">Cargando Revisión…</p></section>;
  if (review.isError) return <section className="review-page"><h1>Revisión</h1><div role="alert"><p>No pudimos cargar la Revisión.</p><button type="button" onClick={() => void review.refetch()}>Reintentar</button></div></section>;

  const data = review.data;
  const pendingChanges = data.pending_items.flatMap((row) => {
    const edit = editFor(row, pendingEdits);
    const change = changedPendingEdit(row, edit);
    return Object.keys(change).length ? [{ pending_item_id: row.id, ...change, lock_version: row.lock_version }] : [];
  });
  const stageChanges = data.project_stages.flatMap((row) => {
    const edit = editFor(row, stageEdits);
    const change = changedStageEdit(row, edit);
    return Object.keys(change).length ? [{ stage_id: row.id, ...change, lock_version: row.lock_version, project_lock_version: row.project_lock_version }] : [];
  });
  const pendingValid = validProgress(data.pending_items.map((row) => editFor(row, pendingEdits)));
  const stagesValid = validProgress(data.project_stages.map((row) => editFor(row, stageEdits)), true);

  return <section className="review-page">
    <header className="review-header"><div><p className="eyebrow">{formatCalendarDate(data.review_date)}</p><h1>Revisión</h1></div></header>

    <details className="review-section" open><summary><span id="review-tasks-title">Tareas</span><strong aria-label={`${data.tasks.length} tareas`}>{data.tasks.length}</strong></summary><div aria-labelledby="review-tasks-title">
      {data.tasks.length === 0 ? <p className="review-empty">No tienes tareas pendientes para revisar.</p> : <div className="review-task-list">{data.tasks.map((task) => <article className="review-task-row review-task-row--v2" key={task.id}><time dateTime={task.planned_date}>{formatShortCalendarDate(task.planned_date)}</time><span>{task.workspace_name}</span><strong>{task.task_name}</strong><div role="group" aria-label={`Resultado de ${task.task_name}`}>{(["NOT_COMPLETED", "COMPLETED"] as const).map((result) => { const selected = taskResults[task.id] === result; const label = result === "COMPLETED" ? "Completado" : "No realizado"; return <button type="button" className={selected ? "review-result review-result--selected" : "review-result"} aria-pressed={selected} key={result} onClick={() => { setTaskResults((current) => ({ ...current, [task.id]: result })); setTaskFeedback(null); }}>{label}</button>; })}</div></article>)}</div>}
      <FeedbackMessage feedback={taskFeedback} /><div className="review-save"><button className="primary-button" type="button" disabled={!Object.keys(taskResults).length || taskSave.isPending} onClick={() => taskSave.mutate({ items: data.tasks.flatMap((task) => taskResults[task.id] ? [{ task_id: task.id, result: taskResults[task.id], lock_version: task.lock_version }] : []) })}>{taskSave.isPending ? "Guardando…" : "Guardar Tareas"}</button></div>
    </div></details>

    <details className="review-section" open><summary><span id="review-pending-title">Pendientes</span><strong aria-label={`${data.pending_items.length} pendientes`}>{data.pending_items.length}</strong></summary><div aria-labelledby="review-pending-title">
      {data.pending_items.length === 0 ? <p className="review-empty">No tienes pendientes para revisar.</p> : <div className="review-v2-list">{data.pending_items.map((row) => <EditableRow key={row.id} row={row} label="Pendiente" edit={editFor(row, pendingEdits)} onChange={(edit) => { setPendingEdits((current) => ({ ...current, [row.id]: edit })); setPendingFeedback(null); }} />)}</div>}
      {!pendingValid ? <p role="alert" className="review-notice review-notice--error">El avance debe ser un entero entre 0 y 100.</p> : null}<FeedbackMessage feedback={pendingFeedback} /><div className="review-save"><button className="primary-button" type="button" disabled={!pendingChanges.length || !pendingValid || pendingSave.isPending} onClick={() => pendingSave.mutate({ items: pendingChanges })}>{pendingSave.isPending ? "Guardando…" : "Guardar Pendientes"}</button></div>
    </div></details>

    <details className="review-section" open><summary><span id="review-projects-title">Proyectos / Etapas</span><strong aria-label={`${data.project_stages.length} etapas`}>{data.project_stages.length}</strong></summary><div aria-labelledby="review-projects-title">
      {data.project_stages.length === 0 ? <p className="review-empty">No tienes etapas para revisar.</p> : <div className="review-v2-list">{data.project_stages.map((row) => <EditableRow key={row.id} row={row} label="Etapa" edit={editFor(row, stageEdits)} onChange={(edit) => { setStageEdits((current) => ({ ...current, [row.id]: edit })); setStageFeedback(null); }} />)}</div>}
      {!stagesValid ? <p role="alert" className="review-notice review-notice--error">El avance debe tener hasta dos decimales y estar entre 0 y 100.</p> : null}<FeedbackMessage feedback={stageFeedback} /><div className="review-save"><button className="primary-button" type="button" disabled={!stageChanges.length || !stagesValid || stageSave.isPending} onClick={() => stageSave.mutate({ items: stageChanges })}>{stageSave.isPending ? "Guardando…" : "Guardar Proyectos"}</button></div>
    </div></details>
  </section>;
}
