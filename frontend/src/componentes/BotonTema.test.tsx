import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { fijarTema } from "../lib/tema";
import { BotonTema } from "./BotonTema";

afterEach(() => fijarTema("sistema"));

describe("BotonTema", () => {
  it("pasa de claro a oscuro y al revés, y dice qué va a hacer", () => {
    render(<BotonTema />);
    fireEvent.click(screen.getByRole("button", { name: "Cambiar a modo oscuro" }));
    expect(document.documentElement.dataset.tema).toBe("oscuro");

    fireEvent.click(screen.getByRole("button", { name: "Cambiar a modo claro" }));
    expect(document.documentElement.dataset.tema).toBe("claro");
  });
});
