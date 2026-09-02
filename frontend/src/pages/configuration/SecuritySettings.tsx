import axios from "axios";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { changePassword } from "../../api/authApi";
import { useAuth } from "../../hooks/useAuth";

function validatePassword(value: string): string | null {
  if (value.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
  if (value.length > 128) return "La contraseña no debe exceder 128 caracteres.";
  if (!/[A-Z]/u.test(value)) return "Incluye al menos una letra mayúscula.";
  if (!/[a-z]/u.test(value)) return "Incluye al menos una letra minúscula.";
  if (![...value].some((character) => !/^[\p{L}\p{N}\s]$/u.test(character))) return "Incluye al menos un símbolo.";
  return null;
}

export function SecuritySettings() {
  const navigate = useNavigate();
  const { clearSession } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      clearSession();
      navigate("/login", { replace: true, state: { passwordChanged: true } });
    },
    onError: (error) => {
      const code = axios.isAxiosError(error) ? error.response?.data?.error?.code : null;
      setFeedback(code === "CURRENT_PASSWORD_INCORRECT"
        ? "La contraseña actual no es correcta."
        : code === "RATE_LIMITED"
          ? "Demasiados intentos. Inténtalo nuevamente más tarde."
          : "No pudimos cambiar la contraseña. Intenta nuevamente.");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setFeedback(null);
    const violation = validatePassword(newPassword);
    if (violation) {
      setFeedback(violation);
      return;
    }
    if (newPassword !== confirmation) {
      setFeedback("Las contraseñas nuevas no coinciden.");
      return;
    }
    save.mutate({ current_password: currentPassword, new_password: newPassword });
  }

  return <section className="configuration-panel" aria-labelledby="security-heading">
    <h2 id="security-heading">Seguridad</h2>
    <p>Al cambiar tu contraseña se cerrarán las sesiones existentes. Deberás iniciar sesión nuevamente.</p>
    <form className="configuration-form" onSubmit={submit} noValidate>
      <div className="form-field"><label htmlFor="current-password">Contraseña actual</label><input id="current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></div>
      <div className="form-field"><label htmlFor="new-password">Contraseña nueva</label><input id="new-password" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /><small>8–128 caracteres, con mayúscula, minúscula y símbolo.</small></div>
      <div className="form-field"><label htmlFor="confirm-password">Confirmar contraseña nueva</label><input id="confirm-password" type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></div>
      {feedback ? <p className="review-notice review-notice--error" role="alert">{feedback}</p> : null}
      <button className="primary-button" type="submit" disabled={save.isPending || !currentPassword || !newPassword || !confirmation}>{save.isPending ? "Guardando…" : "Cambiar contraseña"}</button>
    </form>
  </section>;
}
