import { afterEach, describe, expect, it } from "vitest";
import { fijarTema, temaEfectivo } from "./tema";

function barra(): HTMLMetaElement {
  const meta = document.createElement("meta");
  meta.name = "theme-color";
  document.head.appendChild(meta);
  return meta;
}

afterEach(() => {
  fijarTema("sistema");
  document.head.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.remove());
});

describe("tema claro u oscuro", () => {
  it("fijar 'oscuro' lo aplica, lo guarda en este dispositivo y pinta la barra del celular", () => {
    const meta = barra();
    fijarTema("oscuro");
    expect(document.documentElement.dataset.tema).toBe("oscuro");
    expect(localStorage.getItem("alarma-hogar:tema")).toBe("oscuro");
    expect(meta.content).toBe("#151a1c");
  });

  it("'Automático' borra la elección y sigue al sistema", () => {
    fijarTema("claro");
    fijarTema("sistema");
    expect(localStorage.getItem("alarma-hogar:tema")).toBeNull();
    // jsdom no tiene preferencia de sistema: queda en claro
    expect(temaEfectivo()).toBe("claro");
    expect(document.documentElement.dataset.tema).toBe("claro");
  });
});
