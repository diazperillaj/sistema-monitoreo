import { clsx, type ClassValue } from "clsx";

/**
 * Une clases condicionales. No resuelve choques entre utilidades de Tailwind (sería otra
 * dependencia en el chunk inicial): cada componente evita pedir dos valores de la misma propiedad.
 */
export function cn(...clases: ClassValue[]): string {
  return clsx(clases);
}
