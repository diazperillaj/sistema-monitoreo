import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Casas from "./Casas";

describe("Casas (página provisional de F0)", () => {
  it("muestra el nombre de la app", () => {
    render(<Casas />);
    expect(screen.getByRole("heading", { name: "Monitoreo del hogar" })).toBeInTheDocument();
  });
});
