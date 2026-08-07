import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import {
  activateProject,
  createProject,
  deactivateProject,
  listProjects,
  updateProject
} from "../../api/projectApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { Project, ProjectActiveFilter, ProjectCreate } from "../../types/project";

const projectSchema = z.object({
  name: z.string().trim().min(1, "Ingresa un nombre.").max(100, "El nombre no puede superar 100 caracteres."),
  description: z.string().trim().max(500, "La descripción no puede superar 500 caracteres.")
});

type ProjectFormValues = z.infer<typeof projectSchema>;
type ProjectFilter = "all" | "active" | "inactive";

function filterToActive(filter: ProjectFilter): ProjectActiveFilter {
  if (filter === "active") return true;
  if (filter === "inactive") return false;
  return null;
}

function toProjectPayload(values: ProjectFormValues): ProjectCreate {
  return {
    name: values.name,
    description: values.description || null
  };
}

function ProjectDialog({
  isPending,
  onClose,
  onSubmit,
  project,
  serverError
}: {
  isPending: boolean;
  onClose: () => void;
  onSubmit: (values: ProjectFormValues) => Promise<void>;
  project: Project | null;
  serverError: string | null;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: project?.name ?? "",
      description: project?.description ?? ""
    }
  });

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isPending) onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [isPending, onClose]);

  return (
    <div className="dialog-backdrop">
      <section
        className="project-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-dialog-title"
      >
        <h2 id="project-dialog-title">{project ? "Editar proyecto" : "Nuevo proyecto"}</h2>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="form-field">
            <label htmlFor="project-name">Nombre</label>
            <input
              id="project-name"
              autoFocus
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? "project-name-error" : undefined}
              {...register("name")}
            />
            {errors.name ? <span className="field-error" id="project-name-error">{errors.name.message}</span> : null}
          </div>
          <div className="form-field">
            <label htmlFor="project-description">Descripción <span className="optional-label">(opcional)</span></label>
            <textarea
              id="project-description"
              rows={4}
              aria-invalid={Boolean(errors.description)}
              aria-describedby={errors.description ? "project-description-error" : undefined}
              {...register("description")}
            />
            {errors.description ? (
              <span className="field-error" id="project-description-error">{errors.description.message}</span>
            ) : null}
          </div>
          {serverError ? <div className="form-alert" role="alert">{serverError}</div> : null}
          <div className="dialog-actions">
            <button className="secondary-button" type="button" disabled={isPending} onClick={onClose}>Cancelar</button>
            <button className="primary-button" type="submit" disabled={isPending}>
              {isPending ? "Guardando…" : "Guardar proyecto"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function ProjectsPage() {
  const { workspace } = useAuth();
  const workspacesQuery = useWorkspaces();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedFilter = searchParams.get("status");
  const filter: ProjectFilter = requestedFilter === "active" || requestedFilter === "inactive"
    ? requestedFilter
    : "all";
  const activeFilter = filterToActive(filter);
  const workspaceId = workspace?.id ?? "";
  const [dialogProject, setDialogProject] = useState<Project | null | undefined>();
  const [formError, setFormError] = useState<string | null>(null);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects(workspaceId, activeFilter),
    queryFn: () => listProjects(workspaceId, activeFilter),
    enabled: Boolean(workspaceId),
    staleTime: 30_000
  });

  const invalidateWorkspaceProjects = () => queryClient.invalidateQueries({
    queryKey: queryKeys.projectsForWorkspace(workspaceId)
  });

  const saveMutation = useMutation({
    mutationFn: (values: ProjectFormValues) => {
      const payload = toProjectPayload(values);
      return dialogProject
        ? updateProject(workspaceId, dialogProject.id, payload)
        : createProject(workspaceId, payload);
    },
    onSuccess: async () => {
      const wasEditing = Boolean(dialogProject);
      await invalidateWorkspaceProjects();
      setDialogProject(undefined);
      setFormError(null);
      setSuccessMessage(wasEditing ? "Proyecto actualizado." : "Proyecto creado.");
    },
    onError: (error) => {
      setFormError(
        axios.isAxiosError(error) && error.response?.status === 409
          ? "Ya existe un proyecto con ese nombre en este espacio."
          : "No pudimos guardar el proyecto. Intenta nuevamente."
      );
    }
  });

  const lifecycleMutation = useMutation({
    mutationFn: ({ activate, project }: { activate: boolean; project: Project }) =>
      activate
        ? activateProject(workspaceId, project.id)
        : deactivateProject(workspaceId, project.id),
    onMutate: () => {
      setLifecycleError(null);
      setSuccessMessage(null);
    },
    onSuccess: async (project) => {
      await invalidateWorkspaceProjects();
      setSuccessMessage(project.is_active ? "Proyecto activado." : "Proyecto desactivado.");
    },
    onError: () => {
      setLifecycleError("No pudimos cambiar el estado del proyecto. Intenta nuevamente.");
    }
  });

  function openCreate() {
    setFormError(null);
    setSuccessMessage(null);
    setDialogProject(null);
  }

  function openEdit(project: Project) {
    setFormError(null);
    setSuccessMessage(null);
    setDialogProject(project);
  }

  if (workspacesQuery.isPending || (workspacesQuery.data?.length && !workspace)) {
    return <div className="project-list-skeleton" role="status" aria-label="Cargando proyectos" />;
  }

  if (!workspace) {
    return (
      <section className="projects-empty" aria-labelledby="projects-no-workspace">
        <h1 id="projects-no-workspace">No hay un espacio de trabajo disponible</h1>
        <p>Necesitas acceso a un espacio para administrar proyectos.</p>
      </section>
    );
  }

  return (
    <div className="projects-page">
      <header className="projects-header">
        <div>
          <p className="eyebrow">{workspace.name}</p>
          <h1>Proyectos</h1>
          <p>Agrupa tus tareas por objetivos o iniciativas dentro de este espacio.</p>
        </div>
        <button className="primary-button projects-create" type="button" onClick={openCreate}>Nuevo proyecto</button>
      </header>

      <div className="project-filters" aria-label="Filtrar proyectos">
        {(["all", "active", "inactive"] as const).map((filterValue) => {
          const labels = { all: "Todos", active: "Activos", inactive: "Inactivos" };
          return (
            <button
              className={filter === filterValue ? "filter-button filter-button--active" : "filter-button"}
              type="button"
              aria-pressed={filter === filterValue}
              key={filterValue}
              onClick={() => setSearchParams(filterValue === "all" ? {} : { status: filterValue })}
            >
              {labels[filterValue]}
            </button>
          );
        })}
      </div>

      {successMessage ? <div className="success-notice" role="status">{successMessage}</div> : null}
      {lifecycleError ? <div className="form-alert" role="alert">{lifecycleError}</div> : null}
      {projectsQuery.isPending ? <div className="project-list-skeleton" role="status" aria-label="Cargando proyectos" /> : null}
      {projectsQuery.isError ? (
        <div className="dashboard-error" role="alert">
          <p>No pudimos cargar los proyectos.</p>
          <button className="secondary-button" type="button" onClick={() => void projectsQuery.refetch()}>Reintentar</button>
        </div>
      ) : null}
      {projectsQuery.data?.length === 0 ? (
        <section className="projects-empty">
          <h2>
            {filter === "all"
              ? "Aún no tienes proyectos."
              : filter === "active"
                ? "No hay proyectos activos."
                : "No hay proyectos inactivos."}
          </h2>
          <p>Los proyectos te ayudan a agrupar tareas relacionadas.</p>
          {filter === "all" ? (
            <button className="secondary-button" type="button" onClick={openCreate}>Crear primer proyecto</button>
          ) : null}
        </section>
      ) : null}
      {projectsQuery.data && projectsQuery.data.length > 0 ? (
        <ul className="project-list" aria-label="Proyectos del espacio de trabajo">
          {projectsQuery.data.map((project) => {
            const isChanging = lifecycleMutation.isPending && lifecycleMutation.variables?.project.id === project.id;
            return (
              <li className="project-card" key={project.id}>
                <div className="project-card__content">
                  <div className="project-card__heading">
                    <h2>{project.name}</h2>
                    <span className={project.is_active ? "status-badge status-badge--active" : "status-badge"}>
                      {project.is_active ? "Activo" : "Inactivo"}
                    </span>
                  </div>
                  {project.description ? <p>{project.description}</p> : <p className="project-card__empty">Sin descripción</p>}
                </div>
                <div className="project-actions">
                  <button className="secondary-button" type="button" onClick={() => openEdit(project)}>Editar {project.name}</button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={isChanging}
                    onClick={() => lifecycleMutation.mutate({ activate: !project.is_active, project })}
                  >
                    {isChanging
                      ? "Actualizando…"
                      : project.is_active
                        ? `Desactivar ${project.name}`
                        : `Activar ${project.name}`}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {dialogProject !== undefined ? (
        <ProjectDialog
          project={dialogProject}
          isPending={saveMutation.isPending}
          serverError={formError}
          onClose={() => {
            if (!saveMutation.isPending) setDialogProject(undefined);
          }}
          onSubmit={async (values) => {
            setFormError(null);
            await saveMutation.mutateAsync(values).catch(() => undefined);
          }}
        />
      ) : null}
    </div>
  );
}
