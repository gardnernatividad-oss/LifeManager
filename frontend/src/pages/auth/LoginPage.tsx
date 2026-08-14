import axios from "axios";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useAuth } from "../../hooks/useAuth";

const loginSchema = z.object({
  email: z.email("Ingresa un correo válido."),
  password: z.string().min(1, "Ingresa tu contraseña.")
});

type LoginFormValues = z.infer<typeof loginSchema>;

interface LoginLocationState {
  from?: { pathname?: string; search?: string; hash?: string };
  registrationSuccess?: boolean;
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    resetField,
    formState: { errors, isSubmitting }
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" }
  });

  const onSubmit = handleSubmit(async (credentials) => {
    setSubmitError(null);
    try {
      await login(credentials);
      const state = location.state as LoginLocationState | null;
      const attemptedLocation = state?.from;
      const destination = attemptedLocation?.pathname
        ? `${attemptedLocation.pathname}${attemptedLocation.search ?? ""}${attemptedLocation.hash ?? ""}`
        : "/inicio";
      navigate(destination, { replace: true });
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        setSubmitError("Credenciales incorrectas.");
      } else {
        setSubmitError("No pudimos conectar con LifeManager. Intenta nuevamente.");
      }
      resetField("password");
    }
  });

  return (
    <section className="login-card" aria-labelledby="login-title">
      <div className="login-brand">LifeManager</div>
      <h1 id="login-title">Iniciar sesión</h1>
      <p className="login-card__intro">Organiza tu planificación y seguimiento diario.</p>
      {(location.state as LoginLocationState | null)?.registrationSuccess ? <p className="review-notice review-notice--success" role="status">Cuenta creada. Ya puedes iniciar sesión.</p> : null}

      {submitError ? <div className="form-alert" role="alert">{submitError}</div> : null}

      <form className="login-form" onSubmit={onSubmit} noValidate>
        <div className="form-field">
          <label htmlFor="email">Correo electrónico</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? "email-error" : undefined}
            {...register("email")}
          />
          {errors.email ? <span id="email-error" className="field-error">{errors.email.message}</span> : null}
        </div>

        <div className="form-field">
          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? "password-error" : undefined}
            {...register("password")}
          />
          {errors.password ? <span id="password-error" className="field-error">{errors.password.message}</span> : null}
        </div>

        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Ingresando…" : "Entrar"}
        </button>
      </form>
    </section>
  );
}
