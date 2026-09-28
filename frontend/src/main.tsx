import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./estilos.css";
import Casas from "./vistas/Casas";

const raiz = document.getElementById("root");
if (!raiz) throw new Error("Falta el elemento #root en index.html");

createRoot(raiz).render(
  <StrictMode>
    <Casas />
  </StrictMode>,
);
