import { Link } from "react-router";

export default function NoEncontrado() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center gap-3 px-4">
      <p className="cifras text-monumental font-semibold text-tinta-3">404</p>
      <h1 className="text-xl font-semibold">Esta página no existe</h1>
      <p className="text-tinta-2">
        Puede que el enlace esté incompleto o que la página ya no esté.
      </p>
      <Link
        to="/"
        className="pulsable mt-2 inline-flex h-11 w-fit items-center rounded-[6px] bg-tinta px-4 font-semibold text-cara"
      >
        Ir al inicio
      </Link>
    </main>
  );
}
