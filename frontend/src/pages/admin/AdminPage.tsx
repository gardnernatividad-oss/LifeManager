import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  approveAccountRequest,
  disableAdminUser,
  listAccountRequests,
  listAdminUsers,
  reactivateAdminUser,
  rejectAccountRequest,
} from "../../api/adminApi";
import { queryKeys } from "../../api/queryKeys";
import type { AccountStatus, AdminUser } from "../../types/admin";

const labels: Record<AccountStatus, string> = {
  PENDING_EMAIL_VERIFICATION: "Pendiente de verificación",
  PENDING_APPROVAL: "Pendiente de aprobación",
  ACTIVE: "Activa",
  REJECTED: "Rechazada",
  DISABLED: "Deshabilitada",
};

function safeMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 403) return "No tienes permisos de administración global.";
    if (error.response?.status === 409) return "La cuenta cambió o ya no admite esta acción. Actualiza e inténtalo nuevamente.";
    if (error.response?.status === 429) return "Se alcanzó el límite de operaciones. Inténtalo más tarde.";
  }
  return "No pudimos completar la operación. Intenta nuevamente.";
}

export function AdminPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<AccountStatus | "">("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const filters = { page, page_size: 25, ...(search.trim() ? { search: search.trim() } : {}), ...(status ? { account_status: status } : {}) };
  const requests = useQuery({ queryKey: queryKeys.adminAccountRequests, queryFn: listAccountRequests });
  const users = useQuery({ queryKey: queryKeys.adminUsers(filters), queryFn: () => listAdminUsers(filters) });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.adminAccountRequests }),
      queryClient.invalidateQueries({ queryKey: queryKeys.adminUsersRoot }),
    ]);
  };
  const action = useMutation({
    mutationFn: (operation: () => Promise<unknown>) => operation(),
    onSuccess: async () => { setFeedback("Operación completada."); await refresh(); },
    onError: async (error) => { setFeedback(safeMessage(error)); await refresh(); },
  });

  function confirmStateChange(user: AdminUser) {
    const operation = user.account_status === "ACTIVE" ? "deshabilitar" : "reactivar";
    if (!window.confirm(`¿Deseas ${operation} la cuenta de ${user.email}?`)) return;
    action.mutate(() => user.account_status === "ACTIVE" ? disableAdminUser(user) : reactivateAdminUser(user));
  }

  return (
    <section className="admin-page page-stack" aria-labelledby="admin-title">
      <header><p className="page-eyebrow">Plataforma</p><h1 id="admin-title">Administración</h1><p>Gestiona solicitudes y estados de cuenta sin acceder a contenido privado.</p></header>
      {feedback ? <p className="review-notice" role="status">{feedback}</p> : null}

      <section className="configuration-panel" aria-labelledby="requests-title">
        <h2 id="requests-title">Solicitudes de registro</h2>
        {requests.isPending ? <p role="status">Cargando solicitudes…</p> : null}
        {requests.isError ? <div role="alert"><p>No pudimos cargar las solicitudes.</p><button type="button" onClick={() => void requests.refetch()}>Reintentar</button></div> : null}
        {requests.data?.items.length === 0 ? <p className="register-empty">No hay solicitudes pendientes.</p> : null}
        {requests.data?.items.map((request) => <article className="admin-account-card" key={request.id}>
          <div><strong>{request.first_name} {request.last_name}</strong><span>{request.email}</span><small>{request.timezone}</small></div>
          <div className="action-row">
            <button className="primary-button" disabled={action.isPending} onClick={() => {
              if (window.confirm(`¿Deseas aprobar la solicitud de ${request.email}?`)) action.mutate(() => approveAccountRequest(request.id));
            }}>Aprobar</button>
            <button className="secondary-button" disabled={action.isPending} onClick={() => {
              if (window.confirm(`¿Deseas rechazar la solicitud de ${request.email}?`)) action.mutate(() => rejectAccountRequest(request.id));
            }}>Rechazar</button>
          </div>
        </article>)}
      </section>

      <section className="configuration-panel" aria-labelledby="users-title">
        <h2 id="users-title">Usuarios</h2>
        <div className="admin-filters">
          <label>Buscar<input value={search} maxLength={100} onChange={(event) => { setSearch(event.target.value); setPage(1); }} /></label>
          <label>Estado<select value={status} onChange={(event) => { setStatus(event.target.value as AccountStatus | ""); setPage(1); }}><option value="">Todos</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>
        {users.isPending ? <p role="status">Cargando usuarios…</p> : null}
        {users.isError ? <div role="alert"><p>No pudimos cargar los usuarios.</p><button type="button" onClick={() => void users.refetch()}>Reintentar</button></div> : null}
        {users.data?.items.length === 0 ? <p className="register-empty">No hay usuarios para estos filtros.</p> : null}
        {users.data?.items.map((user) => <article className="admin-account-card" key={user.id}>
          <div><strong>{user.first_name} {user.last_name}</strong><span>{user.email}</span><small>{labels[user.account_status]}{user.global_role === "GLOBAL_ADMIN" ? " · Administrador global" : ""}</small></div>
          {user.global_role !== "GLOBAL_ADMIN" && ["ACTIVE", "DISABLED"].includes(user.account_status) ? <button className="secondary-button" disabled={action.isPending} onClick={() => confirmStateChange(user)}>{user.account_status === "ACTIVE" ? "Deshabilitar" : "Reactivar"}</button> : null}
        </article>)}
        {users.data ? <footer className="register-pagination"><span>Página {users.data.page} de {Math.max(users.data.total_pages, 1)}</span><div><button disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</button><button disabled={page >= users.data.total_pages} onClick={() => setPage((current) => current + 1)}>Siguiente</button></div></footer> : null}
      </section>
    </section>
  );
}
