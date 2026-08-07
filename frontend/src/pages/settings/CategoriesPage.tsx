import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import {
  activateCategory,
  createCategory,
  deactivateCategory,
  listCategories,
  updateCategory
} from "../../api/categoryApi";
import { queryKeys } from "../../api/queryKeys";
import { useAuth } from "../../hooks/useAuth";
import { useWorkspaces } from "../../hooks/useWorkspaces";
import type { Category, CategoryActiveFilter } from "../../types/category";

const categorySchema = z.object({
  name: z.string().trim().min(1, "Ingresa un nombre.").max(100, "El nombre no puede superar 100 caracteres.")
});

type CategoryFormValues = z.infer<typeof categorySchema>;
type CategoryFilter = "all" | "active" | "inactive";

function filterToActive(filter: CategoryFilter): CategoryActiveFilter {
  if (filter === "active") return true;
  if (filter === "inactive") return false;
  return null;
}

function CategoryDialog({
  category,
  isPending,
  onClose,
  onSubmit,
  serverError
}: {
  category: Category | null;
  isPending: boolean;
  onClose: () => void;
  onSubmit: (values: CategoryFormValues) => Promise<void>;
  serverError: string | null;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<CategoryFormValues>({
    resolver: zodResolver(categorySchema),
    defaultValues: { name: category?.name ?? "" }
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
        className="category-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="category-dialog-title"
      >
        <h2 id="category-dialog-title">
          {category ? "Editar categoría" : "Nueva categoría"}
        </h2>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="form-field">
            <label htmlFor="category-name">Nombre</label>
            <input
              id="category-name"
              autoFocus
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? "category-name-error" : undefined}
              {...register("name")}
            />
            {errors.name ? (
              <span className="field-error" id="category-name-error">
                {errors.name.message}
              </span>
            ) : null}
          </div>
          {serverError ? <div className="form-alert" role="alert">{serverError}</div> : null}
          <div className="dialog-actions">
            <button className="secondary-button" type="button" disabled={isPending} onClick={onClose}>
              Cancelar
            </button>
            <button className="primary-button" type="submit" disabled={isPending}>
              {isPending ? "Guardando…" : "Guardar categoría"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function CategoriesPage() {
  const { workspace } = useAuth();
  const workspacesQuery = useWorkspaces();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedFilter = searchParams.get("status");
  const filter: CategoryFilter = requestedFilter === "active" || requestedFilter === "inactive"
    ? requestedFilter
    : "all";
  const activeFilter = filterToActive(filter);
  const workspaceId = workspace?.id ?? "";
  const [dialogCategory, setDialogCategory] = useState<Category | null | undefined>();
  const [formError, setFormError] = useState<string | null>(null);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const categoriesQuery = useQuery({
    queryKey: queryKeys.categories(workspaceId, activeFilter),
    queryFn: () => listCategories(workspaceId, activeFilter),
    enabled: Boolean(workspaceId),
    staleTime: 30_000
  });

  const invalidateWorkspaceCategories = () => queryClient.invalidateQueries({
    queryKey: queryKeys.categoriesForWorkspace(workspaceId)
  });

  const saveMutation = useMutation({
    mutationFn: (values: CategoryFormValues) => dialogCategory
      ? updateCategory(workspaceId, dialogCategory.id, values)
      : createCategory(workspaceId, values),
    onSuccess: async () => {
      const wasEditing = Boolean(dialogCategory);
      await invalidateWorkspaceCategories();
      setDialogCategory(undefined);
      setFormError(null);
      setSuccessMessage(wasEditing ? "Categoría actualizada." : "Categoría creada.");
    },
    onError: (error) => {
      setFormError(
        axios.isAxiosError(error) && error.response?.status === 409
          ? "Ya existe una categoría con ese nombre en este espacio."
          : "No pudimos guardar la categoría. Intenta nuevamente."
      );
    }
  });

  const lifecycleMutation = useMutation({
    mutationFn: ({ category, activate }: { category: Category; activate: boolean }) =>
      activate
        ? activateCategory(workspaceId, category.id)
        : deactivateCategory(workspaceId, category.id),
    onMutate: () => {
      setLifecycleError(null);
      setSuccessMessage(null);
    },
    onSuccess: async (category) => {
      await invalidateWorkspaceCategories();
      setSuccessMessage(category.is_active ? "Categoría activada." : "Categoría desactivada.");
    },
    onError: () => {
      setLifecycleError("No pudimos cambiar el estado de la categoría. Intenta nuevamente.");
    }
  });

  function selectFilter(nextFilter: CategoryFilter) {
    setSearchParams(nextFilter === "all" ? {} : { status: nextFilter });
  }

  function openCreate() {
    setFormError(null);
    setSuccessMessage(null);
    setDialogCategory(null);
  }

  function openEdit(category: Category) {
    setFormError(null);
    setSuccessMessage(null);
    setDialogCategory(category);
  }

  if (workspacesQuery.isPending || (workspacesQuery.data?.length && !workspace)) {
    return <div className="category-list-skeleton" role="status" aria-label="Cargando categorías" />;
  }

  if (!workspace) {
    return (
      <section className="categories-empty" aria-labelledby="categories-no-workspace">
        <h1 id="categories-no-workspace">No hay un espacio de trabajo disponible</h1>
        <p>Necesitas acceso a un espacio para administrar categorías.</p>
      </section>
    );
  }

  return (
    <div className="categories-page">
      <header className="categories-header">
        <div>
          <p className="eyebrow">{workspace.name}</p>
          <h1>Categorías</h1>
          <p>Organiza tus tareas con categorías dentro de este espacio de trabajo.</p>
        </div>
        <button className="primary-button categories-create" type="button" onClick={openCreate}>
          Nueva categoría
        </button>
      </header>

      <div className="category-filters" aria-label="Filtrar categorías">
        {(["all", "active", "inactive"] as const).map((filterValue) => {
          const labels = { all: "Todas", active: "Activas", inactive: "Inactivas" };
          return (
            <button
              className={filter === filterValue ? "filter-button filter-button--active" : "filter-button"}
              type="button"
              aria-pressed={filter === filterValue}
              key={filterValue}
              onClick={() => selectFilter(filterValue)}
            >
              {labels[filterValue]}
            </button>
          );
        })}
      </div>

      {successMessage ? <div className="success-notice" role="status">{successMessage}</div> : null}
      {lifecycleError ? <div className="form-alert" role="alert">{lifecycleError}</div> : null}

      {categoriesQuery.isPending ? (
        <div className="category-list-skeleton" role="status" aria-label="Cargando categorías" />
      ) : null}
      {categoriesQuery.isError ? (
        <div className="dashboard-error" role="alert">
          <p>No pudimos cargar las categorías.</p>
          <button className="secondary-button" type="button" onClick={() => void categoriesQuery.refetch()}>
            Reintentar
          </button>
        </div>
      ) : null}
      {categoriesQuery.data?.length === 0 ? (
        <section className="categories-empty">
          <h2>
            {filter === "all"
              ? "Aún no tienes categorías."
              : filter === "active"
                ? "No hay categorías activas."
                : "No hay categorías inactivas."}
          </h2>
          <p>Las categorías te ayudan a organizar tus tareas.</p>
          {filter === "all" ? (
            <button className="secondary-button" type="button" onClick={openCreate}>
              Crear primera categoría
            </button>
          ) : null}
        </section>
      ) : null}
      {categoriesQuery.data && categoriesQuery.data.length > 0 ? (
        <ul className="category-list" aria-label="Categorías del espacio de trabajo">
          {categoriesQuery.data.map((category) => {
            const isChanging = lifecycleMutation.isPending &&
              lifecycleMutation.variables?.category.id === category.id;
            return (
              <li className="category-card" key={category.id}>
                <div>
                  <h2>{category.name}</h2>
                  <span className={category.is_active ? "status-badge status-badge--active" : "status-badge"}>
                    {category.is_active ? "Activa" : "Inactiva"}
                  </span>
                </div>
                <div className="category-actions">
                  <button className="secondary-button" type="button" onClick={() => openEdit(category)}>
                    Editar {category.name}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={isChanging}
                    onClick={() => lifecycleMutation.mutate({ category, activate: !category.is_active })}
                  >
                    {isChanging
                      ? "Actualizando…"
                      : category.is_active
                        ? `Desactivar ${category.name}`
                        : `Activar ${category.name}`}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {dialogCategory !== undefined ? (
        <CategoryDialog
          category={dialogCategory}
          isPending={saveMutation.isPending}
          serverError={formError}
          onClose={() => {
            if (!saveMutation.isPending) setDialogCategory(undefined);
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
