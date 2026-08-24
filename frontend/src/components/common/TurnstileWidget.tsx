import { useEffect, useRef, useState } from "react";

const scriptId = "cloudflare-turnstile-script";
const scriptUrl = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render: (container: HTMLElement, options: {
    sitekey: string;
    callback: (token: string) => void;
    "expired-callback": () => void;
    "error-callback": () => void;
  }) => string;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

interface TurnstileWidgetProps {
  siteKey: string | null;
  resetSignal: number;
  onTokenChange: (token: string | null) => void;
}

export function TurnstileWidget({ siteKey, resetSignal, onTokenChange }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [retryAttempt, setRetryAttempt] = useState(0);

  useEffect(() => {
    if (!siteKey) return;
    let widgetId: string | null = null;
    let cancelled = false;
    const renderWidget = () => {
      if (cancelled || !window.turnstile || !containerRef.current) return;
      widgetId = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        callback: (token) => onTokenChange(token),
        "expired-callback": () => onTokenChange(null),
        "error-callback": () => {
          onTokenChange(null);
          setLoadFailed(true);
        },
      });
    };
    const existing = document.getElementById(scriptId) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    const onLoad = () => renderWidget();
    const onError = () => setLoadFailed(true);
    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
    if (!existing) {
      script.id = scriptId;
      script.src = scriptUrl;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    if (window.turnstile) {
      renderWidget();
    }
    return () => {
      cancelled = true;
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
      onTokenChange(null);
    };
  }, [onTokenChange, resetSignal, retryAttempt, siteKey]);

  if (!siteKey) return null;
  return <div className="form-field" aria-label="Verificación anti-bot">
    <div ref={containerRef} />
    {loadFailed ? <div role="alert">
      <span className="field-error">No pudimos cargar la verificación anti-bot.</span>
      <button className="secondary-button" type="button" onClick={() => {
        if (!window.turnstile) document.getElementById(scriptId)?.remove();
        setLoadFailed(false);
        setRetryAttempt((value) => value + 1);
      }}>Reintentar</button>
    </div> : null}
  </div>;
}
