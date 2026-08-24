import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TurnstileWidget } from "./TurnstileWidget";

describe("TurnstileWidget", () => {
  afterEach(() => {
    delete window.turnstile;
    document.getElementById("cloudflare-turnstile-script")?.remove();
  });

  it("stays absent when no public site key is configured", () => {
    render(<TurnstileWidget siteKey={null} resetSignal={0} onTokenChange={vi.fn()} />);
    expect(screen.queryByLabelText("Verificación anti-bot")).not.toBeInTheDocument();
  });

  it("returns only the ephemeral widget token and removes the widget", () => {
    const onTokenChange = vi.fn();
    const remove = vi.fn();
    window.turnstile = {
      render: vi.fn((_container, options) => {
        options.callback("ephemeral-response");
        return "widget-id";
      }),
      remove,
    };
    const view = render(<TurnstileWidget siteKey="public-site-key" resetSignal={0} onTokenChange={onTokenChange} />);
    expect(screen.getByLabelText("Verificación anti-bot")).toBeInTheDocument();
    expect(onTokenChange).toHaveBeenCalledWith("ephemeral-response");
    act(() => view.unmount());
    expect(remove).toHaveBeenCalledWith("widget-id");
  });

  it("offers a safe retry when the provider script fails", () => {
    render(<TurnstileWidget siteKey="public-site-key" resetSignal={0} onTokenChange={vi.fn()} />);
    const firstScript = document.getElementById("cloudflare-turnstile-script");
    fireEvent.error(firstScript!);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(document.getElementById("cloudflare-turnstile-script")).not.toBe(firstScript);
  });
});
