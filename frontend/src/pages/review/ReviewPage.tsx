import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type Dispatch, type SetStateAction } from "react";

import { queryKeys } from "../../api/queryKeys";
import { getReview, saveReview } from "../../api/reviewApi";
import { useAuth } from "../../hooks/useAuth";
import type { ReviewEditableRow, ReviewProjectStep, ReviewSave, ReviewTaskResult } from "../../types/review";
import { formatCalendarDate, formatLocalTimestamp, formatShortCalendarDate } from "../../utils/localizedDate";

interface LocalEdit { progress: string; comment: string }
type EditMap = Record<string, LocalEdit>;

function editFor(row: ReviewEditableRow | ReviewProjectStep, edits: EditMap): LocalEdit {
  return edits[row.id] ?? {
    progress: String(row.progress),
    comment: row.comment ?? ""
  };
}

function changedUpdate(row: ReviewEditableRow | ReviewProjectStep, edit: LocalEdit) {
  const update: { id: string; progress?: number; comment?: string | null; lock_version: number } = {
    id: row.id,
    lock_version: row.lock_version
  };
  const progress = Number(edit.progress);
  if (progress !== row.progress) update.progress = progress;
  if (edit.comment !== (row.comment ?? "")) update.comment = edit.comment.trim() || null;
  return Object.keys(update).length > 2 ? update : null;
}

function ReviewLoading() {
  return (
    <section className="review-page" aria-label="Revisión">
      <div className="review-skeleton" role="status" aria-label="Cargando Revisión">
        <span>Cargando Revisión…</span>
      </div>
    </section>
  );
}

function EditableRow({
  edit,
  kind,
  onChange,
  row
}: {
  edit: LocalEdit;
  kind: "Pendiente" | "Paso";
  onChange: (edit: LocalEdit) => void;
  row: ReviewEditableRow | ReviewProjectStep;
}) {
  return (
    <div className={`review-data-row review-data-row--${kind === "Paso" ? "step" : "pending"}`} role="row">
      <span role="cell" data-label="Fecha planificada">{formatShortCalendarDate(row.planned_date)}</span>
      <strong role="cell" data-label={kind}>{row.name}</strong>
      {"weight" in row ? <span role="cell" data-label="Peso">{row.weight}%</span> : null}
      <label role="cell">
        <span className="sr-only">Avance de {row.name}</span>
        <input
          aria-label={`Avance de ${row.name}`}
          inputMode="numeric"
          min="0"
          max="100"
          step="1"
          type="number"
          value={edit.progress}
          onChange={(event) => onChange({ ...edit, progress: event.target.value })}
        />
      </label>
      <label role="cell">
        <span className="sr-only">Comentario de {row.name}</span>
        <input
          aria-label={`Comentario de ${row.name}`}
          type="text"
          value={edit.comment}
          onChange={(event) => onChange({ ...edit, comment: event.target.value })}
        />
      </label>
    </div>
  );
}

export function ReviewPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const reviewQuery = useQuery({ queryKey: queryKeys.review, queryFn: getReview });
  const [taskResults, setTaskResults] = useState<Record<string, ReviewTaskResult>>({});
  const [pendingEdits, setPendingEdits] = useState<EditMap>({});
  const [stepEdits, setStepEdits] = useState<EditMap>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: (payload: ReviewSave) => saveReview(payload),
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.home });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.taskReportsRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.pendingItemReportsRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.projectReportsRoot })
      ]);
      await queryClient.refetchQueries({ queryKey: queryKeys.review });
      setTaskResults({});
      setPendingEdits({});
      setStepEdits({});
      setNotice("Revisión guardada.");
    },
    onError: (caught) => {
      setNotice(null);
      setError(
        axios.isAxiosError(caught) && caught.response?.status === 409
          ? "Parte de la información cambió. Conservamos tus cambios; actualiza la página y vuelve a intentarlo."
          : "No pudimos guardar la Revisión. Tus cambios siguen disponibles para reintentar."
      );
    }
  });

  if (reviewQuery.isPending) return <ReviewLoading />;
  if (reviewQuery.isError) {
    return (
      <section className="review-page">
        <h1>Revisión</h1>
        <div className="review-error" role="alert">
          <p>No pudimos cargar la Revisión.</p>
          <button className="secondary-button" type="button" onClick={() => void reviewQuery.refetch()}>Reintentar</button>
        </div>
      </section>
    );
  }

  const review = reviewQuery.data;
  const steps = review.projects.flatMap((project) => project.steps);
  const isEmpty = review.tasks.length === 0 && review.pending_items.length === 0 && steps.length === 0;

  function setEdit(setter: Dispatch<SetStateAction<EditMap>>, id: string, edit: LocalEdit) {
    setter((current) => ({ ...current, [id]: edit }));
    setNotice(null);
  }

  function submit() {
    const allEdits = [
      ...review.pending_items.map((row) => editFor(row, pendingEdits)),
      ...steps.map((row) => editFor(row, stepEdits))
    ];
    if (allEdits.some((edit) => !edit || !Number.isInteger(Number(edit.progress)) || Number(edit.progress) < 0 || Number(edit.progress) > 100)) {
      setError("El avance debe ser un número entero entre 0 y 100.");
      return;
    }
    const payload: ReviewSave = {
      tasks: review.tasks.flatMap((task) => taskResults[task.id]
        ? [{ id: task.id, result: taskResults[task.id], lock_version: task.lock_version }]
        : []),
      pending_items: review.pending_items.flatMap((row) => {
        const update = changedUpdate(row, editFor(row, pendingEdits));
        return update ? [update] : [];
      }),
      project_steps: steps.flatMap((row) => {
        const update = changedUpdate(row, editFor(row, stepEdits));
        return update ? [update] : [];
      })
    };
    setError(null);
    setNotice(null);
    saveMutation.mutate(payload);
  }

  return (
    <section className="review-page">
      <header className="review-header">
        <div>
          <p className="eyebrow">{formatCalendarDate(review.review_date)}</p>
          <h1>Revisión</h1>
        </div>
        <dl>
          <dt>Última revisión</dt>
          <dd>{formatLocalTimestamp(review.last_review_saved_at, user?.timezone ?? "UTC")}</dd>
        </dl>
      </header>

      {isEmpty ? <p className="review-empty">No hay elementos que requieran revisión hoy.</p> : null}

      {review.tasks.length > 0 ? (
        <section className="review-section" aria-labelledby="review-tasks-title">
          <h2 id="review-tasks-title">Tareas</h2>
          <div className="review-task-list">
            {review.tasks.map((task) => (
              <div className="review-task-row" key={task.id}>
                <time dateTime={task.planned_date}>{formatShortCalendarDate(task.planned_date)}</time>
                <strong>{task.name}</strong>
                {(["NOT_COMPLETED", "COMPLETED"] as const).map((result) => {
                  const label = result === "COMPLETED" ? "Completado" : "No realizado";
                  const selected = taskResults[task.id] === result;
                  return (
                    <button
                      type="button"
                      className={selected ? "review-result review-result--selected" : "review-result"}
                      aria-label={`${label}: ${task.name}`}
                      aria-pressed={selected}
                      key={result}
                      onClick={() => { setTaskResults((current) => ({ ...current, [task.id]: result })); setNotice(null); }}
                    >{label}</button>
                  );
                })}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {review.pending_items.length > 0 ? (
        <section className="review-section" aria-labelledby="review-pending-title">
          <h2 id="review-pending-title">Pendientes</h2>
          <div className="review-table" role="table" aria-label="Pendientes para revisión">
            <div className="review-table-head review-data-row review-data-row--pending" role="row">
              <span role="columnheader">Fecha planificada</span><span role="columnheader">Pendiente</span><span role="columnheader">Avance</span><span role="columnheader">Comentario</span>
            </div>
            {review.pending_items.map((row) => <EditableRow edit={editFor(row, pendingEdits)} kind="Pendiente" key={row.id} row={row} onChange={(edit) => setEdit(setPendingEdits, row.id, edit)} />)}
          </div>
        </section>
      ) : null}

      {review.projects.length > 0 ? (
        <section className="review-section" aria-labelledby="review-projects-title">
          <h2 id="review-projects-title">Proyectos</h2>
          <div className="review-projects">
            {review.projects.map((project) => (
              <section aria-labelledby={`review-project-${project.id}`} className="review-project" key={project.id}>
                <h3 id={`review-project-${project.id}`}>{project.name}</h3>
                <div className="review-table" role="table" aria-label={`Pasos de ${project.name}`}>
                  <div className="review-table-head review-data-row review-data-row--step" role="row">
                    <span role="columnheader">Fecha planificada</span><span role="columnheader">Paso</span><span role="columnheader">Peso</span><span role="columnheader">Avance</span><span role="columnheader">Comentario</span>
                  </div>
                  {project.steps.map((row) => <EditableRow edit={editFor(row, stepEdits)} kind="Paso" key={row.id} row={row} onChange={(edit) => setEdit(setStepEdits, row.id, edit)} />)}
                </div>
              </section>
            ))}
          </div>
        </section>
      ) : null}

      {error ? <p className="review-notice review-notice--error" role="alert">{error}</p> : null}
      {notice ? <p className="review-notice review-notice--success" role="status">{notice}</p> : null}
      <div className="review-save">
        <button className="primary-button" type="button" disabled={saveMutation.isPending} onClick={submit}>
          {saveMutation.isPending ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </section>
  );
}
