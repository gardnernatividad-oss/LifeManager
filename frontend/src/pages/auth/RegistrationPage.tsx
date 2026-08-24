import axios from "axios";
import { zodResolver } from "@hookform/resolvers/zod";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { registerUser } from "../../api/authApi";
import { TurnstileWidget } from "../../components/common/TurnstileWidget";
import { env } from "../../utils/env";

const registrationSchema = z.object({
  first_name: z.string().trim().min(1, "Ingresa tu nombre."),
  last_name: z.string().trim().min(1, "Ingresa tu apellido."),
  email: z.email("Ingresa un correo válido."),
  password: z.string().min(1, "Ingresa una contraseña."),
  password_confirmation: z.string().min(1, "Confirma tu contraseña."),
}).refine((values) => values.password === values.password_confirmation, {
  path: ["password_confirmation"],
  message: "Las contraseñas no coinciden.",
});

type RegistrationValues = z.infer<typeof registrationSchema>;

export function RegistrationPage() {
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileReset, setTurnstileReset] = useState(0);
  const handleTurnstileToken = useCallback(
    (token: string | null) => setTurnstileToken(token),
    [],
  );
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<RegistrationValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: { first_name: "", last_name: "", email: "", password: "", password_confirmation: "" },
  });

  const submit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await registerUser({
        email: values.email,
        password: values.password,
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        ...(turnstileToken ? { turnstile_token: turnstileToken } : {}),
      });
      navigate("/login", { replace: true, state: { registrationSuccess: true } });
    } catch (error) {
      setTurnstileToken(null);
      setTurnstileReset((value) => value + 1);
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setSubmitError("Ya existe una cuenta con ese correo electrónico.");
      } else if (axios.isAxiosError(error) && error.response?.status === 422) {
        setSubmitError("Revisa los datos ingresados e intenta nuevamente.");
      } else {
        setSubmitError("No pudimos crear la cuenta. Intenta nuevamente.");
      }
    }
  });

  return <section className="login-card registration-card" aria-labelledby="registration-title">
    <div className="login-brand">LifeManager</div>
    <h1 id="registration-title">Crear cuenta</h1>
    <p className="login-card__intro">Empieza a organizar tu planificación personal.</p>
    {submitError ? <div className="form-alert" role="alert">{submitError}</div> : null}
    <form className="login-form" onSubmit={submit} noValidate>
      <div className="registration-name-grid">
        <div className="form-field"><label htmlFor="registration-first-name">Nombre</label><input id="registration-first-name" autoComplete="given-name" aria-invalid={Boolean(errors.first_name)} {...register("first_name")} />{errors.first_name ? <span className="field-error">{errors.first_name.message}</span> : null}</div>
        <div className="form-field"><label htmlFor="registration-last-name">Apellido</label><input id="registration-last-name" autoComplete="family-name" aria-invalid={Boolean(errors.last_name)} {...register("last_name")} />{errors.last_name ? <span className="field-error">{errors.last_name.message}</span> : null}</div>
      </div>
      <div className="form-field"><label htmlFor="registration-email">Correo electrónico</label><input id="registration-email" type="email" autoComplete="email" aria-invalid={Boolean(errors.email)} {...register("email")} />{errors.email ? <span className="field-error">{errors.email.message}</span> : null}</div>
      <div className="form-field"><label htmlFor="registration-password">Contraseña</label><input id="registration-password" type="password" autoComplete="new-password" aria-invalid={Boolean(errors.password)} {...register("password")} />{errors.password ? <span className="field-error">{errors.password.message}</span> : null}</div>
      <div className="form-field"><label htmlFor="registration-confirmation">Confirmar contraseña</label><input id="registration-confirmation" type="password" autoComplete="new-password" aria-invalid={Boolean(errors.password_confirmation)} {...register("password_confirmation")} />{errors.password_confirmation ? <span className="field-error">{errors.password_confirmation.message}</span> : null}</div>
      <TurnstileWidget siteKey={env.turnstileSiteKey} resetSignal={turnstileReset} onTokenChange={handleTurnstileToken} />
      <button className="primary-button" type="submit" disabled={isSubmitting || Boolean(env.turnstileSiteKey && !turnstileToken)}>{isSubmitting ? "Creando…" : "Crear cuenta"}</button>
    </form>
  </section>;
}
