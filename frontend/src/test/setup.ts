import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { servidor } from "./servidor";

// jsdom no trae ResizeObserver, que usan los interruptores de Radix para medirse
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverFalso as unknown as typeof ResizeObserver;

// La API simulada con MSW (§13.5): cada prueba agrega sus respuestas con servidor.use()
beforeAll(() => servidor.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup(); // sin "globals" de Vitest, Testing Library no limpia sola entre pruebas
  servidor.resetHandlers();
  localStorage.clear();
});
afterAll(() => servidor.close());
