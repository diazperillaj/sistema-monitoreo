import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import "./estilos.css";
import Casas from "./vistas/Casas";

// El service worker solo existe en el build (FastAPI en :8011), no con npm run dev
if (import.meta.env.PROD) registerSW({ immediate: true });

const raiz = document.getElementById("root");
if (!raiz) throw new Error("Falta el elemento #root en index.html");

createRoot(raiz).render(
  <StrictMode>
    <Casas />
  </StrictMode>,
);
