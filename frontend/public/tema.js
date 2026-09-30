/*
 * Aplica el modo claro u oscuro antes de pintar la página, para que de noche no haya un
 * destello blanco. Va aparte (no en línea) porque la CSP no permite scripts en línea (§6.7).
 * Después lo retoma src/lib/tema.ts, que guarda la elección y sigue los cambios del sistema.
 */
(function () {
  var preferencia = null;
  try {
    preferencia = localStorage.getItem("alarma-hogar:tema");
  } catch (error) {
    // sin almacenamiento (modo privado): sigue el modo del dispositivo
  }
  var oscuro =
    preferencia === "oscuro" ||
    (preferencia !== "claro" &&
      !!window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-tema", oscuro ? "oscuro" : "claro");
  var barras = document.querySelectorAll('meta[name="theme-color"]');
  for (var i = 0; i < barras.length; i++) {
    barras[i].setAttribute("content", oscuro ? "#151a1c" : "#f9fbfa");
  }
})();
