import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";

import { getDailyFormDefinition, getDailyFormSubmission, putDailyFormSubmission } from "../../api/dailyFormApi";
import { evaluateDailyWorkflow } from "../../api/dailyWorkflowApi";
import { queryKeys } from "../../api/queryKeys";
import { getWorkspaceSettings } from "../../api/workspaceSettingsApi";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { DailyFormDefinition, DailyFormSubmission, DailyFormSubmissionPayload } from "../../types/dailyForm";
import type { DailyWorkflow } from "../../types/dailyWorkflow";
import { formatWorkspaceDate, isDateOnly, shiftDate, workspaceToday } from "../../utils/workspaceDate";

type AnswerFields = Record<string, string>;

function safeApiMessage(error: unknown, action: string) {
  if (axios.isAxiosError(error) && (error.response?.status === 409 || error.response?.status === 422)) return `No pudimos ${action}. Revisa todas las respuestas e intenta nuevamente.`;
  return `No pudimos ${action}. Verifica la conexión e intenta nuevamente.`;
}

function defaultAnswers(definition: DailyFormDefinition, submission: DailyFormSubmission | null): AnswerFields {
  const saved = new Map(submission?.answers.map((answer) => [answer.question_id, answer.value]) ?? []);
  return Object.fromEntries(definition.questions.map((question) => {
    const value = saved.get(question.id);
    return [question.id, value === undefined ? "" : String(value)];
  }));
}

function DailyAnswersForm({ definition, submission, pending, error, onSubmit }: {
  definition: DailyFormDefinition; submission: DailyFormSubmission | null; pending: boolean; error: string | null;
  onSubmit: (payload: DailyFormSubmissionPayload) => Promise<void>;
}) {
  const ordered = useMemo(() => [...definition.questions].sort((a, b) => a.order - b.order), [definition.questions]);
  const { register, handleSubmit, formState: { errors } } = useForm<AnswerFields>({ defaultValues: defaultAnswers(definition, submission) });
  return <form className="daily-form" noValidate onSubmit={handleSubmit(async (values) => {
    const answers = ordered.map((question) => ({ question_id: question.id, value: question.answer_type === "boolean" ? values[question.id] === "true" : question.answer_type === "number" ? Number(values[question.id]) : values[question.id] }));
    await onSubmit({ answers });
  })}>
    {ordered.map((question) => <div className="daily-question" key={question.id}>
      {question.answer_type === "boolean" ? <fieldset><legend>{question.order}. {question.title}</legend>{question.description && <p>{question.description}</p>}<div className="boolean-options"><label><input type="radio" value="true" {...register(question.id, { required: "Selecciona Sí o No." })} />Sí</label><label><input type="radio" value="false" {...register(question.id, { required: "Selecciona Sí o No." })} />No</label></div></fieldset> : <div className="form-field"><label htmlFor={`answer-${question.id}`}>{question.order}. {question.title}</label>{question.description && <p>{question.description}</p>}{question.answer_type === "number" ? <input id={`answer-${question.id}`} type="number" step="any" {...register(question.id, { required: "Ingresa una respuesta.", validate: (value) => Number.isFinite(Number(value)) || "Ingresa un número válido." })} /> : <textarea id={`answer-${question.id}`} rows={3} {...register(question.id, { required: "Ingresa una respuesta." })} />}</div>}
      {errors[question.id] && <span className="field-error" role="alert">{errors[question.id]?.message}</span>}
    </div>)}
    {error && <div className="form-alert" role="alert">{error}</div>}
    <button className="primary-button" type="submit" disabled={pending}>{pending ? "Guardando respuestas…" : submission ? "Guardar cambios" : "Enviar formulario"}</button>
  </form>;
}

function HistoricalSubmission({ submission }: { submission: DailyFormSubmission }) {
  return <section className="historical-submission" aria-labelledby="historical-title"><h3 id="historical-title">Respuestas guardadas</h3><dl>{[...submission.answers].sort((a, b) => a.question_order - b.question_order).map((answer) => <div key={answer.question_id}><dt>{answer.question_order}. {answer.question_title}</dt><dd>{typeof answer.value === "boolean" ? answer.value ? "Sí" : "No" : answer.value}</dd></div>)}</dl></section>;
}

export function DailyWorkflowPage() {
  const { workspace } = useAuth(); const workspaces = useWorkspaces(); const queryClient = useQueryClient(); const [params, setParams] = useSearchParams();
  const workspaceId = workspace?.id ?? ""; const today = workspace ? workspaceToday(workspace.timezone) : "";
  const requestedDate = params.get("date"); const date = isDateOnly(requestedDate) ? requestedDate : today;
  const [saveError, setSaveError] = useState<string | null>(null); const [success, setSuccess] = useState<string | null>(null);
  const [workflowState, setWorkflowState] = useState<{ workspaceId: string; date: string; value: DailyWorkflow } | null>(null);

  const settingsQuery = useQuery({ queryKey: queryKeys.workspaceSettings(workspaceId), queryFn: () => getWorkspaceSettings(workspaceId), enabled: !!workspaceId });
  const definitionQuery = useQuery({ queryKey: queryKeys.dailyFormDefinition(workspaceId), queryFn: () => getDailyFormDefinition(workspaceId), enabled: !!workspaceId && settingsQuery.data?.daily_form_enabled === true });
  const submissionQuery = useQuery({ queryKey: queryKeys.dailyFormSubmission(workspaceId, date), queryFn: () => getDailyFormSubmission(workspaceId, date), enabled: !!workspaceId && !!date && settingsQuery.data?.daily_form_enabled === true });
  const workflowMutation = useMutation({ mutationFn: ({ id, day }: { id: string; day: string }) => evaluateDailyWorkflow(id, day), onSuccess: async (workflow) => { setWorkflowState({ workspaceId: workflow.workspace_id, date: workflow.workflow_date, value: workflow }); queryClient.setQueryData(queryKeys.dailyWorkflow(workflow.workspace_id, workflow.workflow_date), workflow); if (workflow.task_generation.created_task_count > 0) await Promise.all([queryClient.invalidateQueries({ queryKey: queryKeys.tasksForWorkspace(workflow.workspace_id) }), queryClient.invalidateQueries({ queryKey: queryKeys.dashboardSummary(workflow.workspace_id) }), queryClient.invalidateQueries({ queryKey: queryKeys.dashboardStatistics(workflow.workspace_id) })]); }, onError: () => undefined });
  const evaluate = workflowMutation.mutate;
  useEffect(() => { if (workspaceId && date) evaluate({ id: workspaceId, day: date }); }, [workspaceId, date, evaluate]);
  const workflow = workflowState?.workspaceId === workspaceId && workflowState.date === date ? workflowState.value : null;

  const submissionMutation = useMutation({ mutationFn: (payload: DailyFormSubmissionPayload) => putDailyFormSubmission(workspaceId, date, payload), onSuccess: async (saved) => { queryClient.setQueryData(queryKeys.dailyFormSubmission(workspaceId, date), saved); await queryClient.invalidateQueries({ queryKey: queryKeys.dailyFormSubmission(workspaceId, date) }); setSaveError(null); setSuccess(submissionQuery.data ? "Respuestas actualizadas." : "Formulario enviado."); evaluate({ id: workspaceId, day: date }); }, onError: (error) => setSaveError(safeApiMessage(error, "guardar las respuestas")) });

  const selectDate = (next: string) => { setSuccess(null); setParams({ date: next }); };
  if (workspaces.isPending || (workspaces.data?.length && !workspace)) return <div className="workflow-skeleton" role="status" aria-label="Cargando seguimiento diario" />;
  if (!workspace) return <section className="workflow-empty"><h1>No hay un espacio de trabajo disponible</h1><p>Selecciona un espacio para realizar el seguimiento diario.</p></section>;
  const loading = workflowMutation.isPending && !workflow;
  const definition = definitionQuery.data ?? null; const submission = submissionQuery.data ?? null;
  return <div className="workflow-page"><header className="workflow-header"><div><p className="eyebrow">{workspace.name}</p><h1>Seguimiento diario</h1><p>{formatWorkspaceDate(date)} · {workspace.timezone}</p></div><div className="workflow-date-controls"><button className="secondary-button" aria-label="Día anterior" onClick={() => selectDate(shiftDate(date, -1))}>Anterior</button><label htmlFor="workflow-date">Fecha<input id="workflow-date" type="date" value={date} onChange={(event) => selectDate(event.target.value)} /></label><button className="secondary-button" aria-label="Día siguiente" onClick={() => selectDate(shiftDate(date, 1))}>Próximo</button><button className="secondary-button" onClick={() => selectDate(today)}>Hoy</button><button className="secondary-button" disabled={workflowMutation.isPending} onClick={() => evaluate({ id: workspaceId, day: date })}>{workflowMutation.isPending ? "Actualizando…" : "Actualizar"}</button></div></header>
    {loading && <div className="workflow-skeleton" role="status" aria-label="Evaluando seguimiento diario" />}
    {workflowMutation.isError && <div className="dashboard-error" role="alert"><p>No pudimos evaluar el seguimiento diario.</p><button className="secondary-button" onClick={() => evaluate({ id: workspaceId, day: date })}>Reintentar</button></div>}
    {workflow && <><div className="workflow-summary-grid"><article className={`workflow-status workflow-status--${workflow.workflow_status.toLowerCase()}`}><span>Estado</span><h2>{workflow.workflow_status === "READY" ? "Listo" : "Acción requerida"}</h2><p>{workflow.workflow_status === "READY" ? "No hay acciones pendientes del formulario diario." : "Completa el formulario diario para finalizar este seguimiento."}</p><small>Evaluado {new Intl.DateTimeFormat("es-PE", { dateStyle: "short", timeStyle: "short" }).format(new Date(workflow.evaluated_at))}</small></article><article className="generation-card"><span>Generación de tareas</span><strong>{workflow.task_generation.created_task_count}</strong><p>{workflow.task_generation.created_task_count ? `Se generaron ${workflow.task_generation.created_task_count} tareas recurrentes para este día.` : "No había tareas recurrentes nuevas para generar."}</p><dl><div><dt>Series elegibles</dt><dd>{workflow.task_generation.eligible_series_count}</dd></div><div><dt>Ya existentes</dt><dd>{workflow.task_generation.skipped_existing_count}</dd></div></dl></article></div>
      <section className="daily-form-section" aria-labelledby="daily-form-title"><h2 id="daily-form-title">Formulario diario</h2>
        {settingsQuery.isPending && <div role="status">Cargando configuración…</div>}{settingsQuery.isError && <div className="form-alert" role="alert">No pudimos cargar la configuración del espacio.</div>}
        {settingsQuery.data && !settingsQuery.data.daily_form_enabled && <div className="workflow-empty"><h3>Formulario desactivado</h3><p>La configuración del espacio no requiere formulario diario.</p></div>}
        {settingsQuery.data?.daily_form_enabled && definitionQuery.isPending && <div role="status">Cargando formulario…</div>}
        {definitionQuery.isError && <div className="form-alert" role="alert">No pudimos cargar el formulario diario.</div>}
        {settingsQuery.data?.daily_form_enabled && !definitionQuery.isPending && !definitionQuery.isError && !definition && <div className="workflow-empty"><h3>No hay un formulario configurado</h3><p>El seguimiento permanece listo hasta que exista una definición activa.</p>{submission && <HistoricalSubmission submission={submission} />}</div>}
        {definition && submissionQuery.isPending && <div role="status">Cargando respuestas…</div>}{submissionQuery.isError && <div className="form-alert" role="alert">No pudimos cargar las respuestas guardadas.</div>}
        {definition && !submissionQuery.isPending && !submissionQuery.isError && <><p className="submission-state">{submission ? "Formulario enviado. Puedes reemplazar las respuestas de esta fecha." : "Completa todas las preguntas para enviar el formulario."}</p>{success && <div className="success-notice" role="status">{success}</div>}<DailyAnswersForm key={`${definition.id}-${submission?.updated_at ?? "new"}`} definition={definition} submission={submission?.definition_id === definition.id ? submission : null} pending={submissionMutation.isPending} error={saveError} onSubmit={async (payload) => { await submissionMutation.mutateAsync(payload).catch(() => undefined); }} />{submission && submission.definition_id !== definition.id && <HistoricalSubmission submission={submission} />}</>}
      </section></>}
  </div>;
}
