import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import { AppProviders } from "./store/AppProviders";
import "./styles/global.css";

registerSW({ immediate: true });

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element was not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <AppProviders />
  </StrictMode>
);
