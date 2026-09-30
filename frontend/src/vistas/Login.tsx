/**
 * Entrar (§11.2). Tras entrar vuelve a ?volver= (solo rutas de esta app) o al inicio.
 * Olvidar la clave no tiene autoservicio: la restablece quien administra el sistema (§12.1).
 */
import { useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router";
import { mensajeDe } from "../api/cliente";
import { useEntrar, useYo } from "../api/consultas";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";

/** Solo rutas internas: "/casa/1" sí; "//otro.sitio" o "https://…" no. */
export function rutaSegura(volver: string | null): string {
  if (!volver || !volver.startsWith("/") || volver.startsWith("//") || volver.startsWith("/\\")) {
    return "/";
  }
  return volver.startsWith("/login") ? "/" : volver;
}

export default function Login() {
  const [parametros] = useSearchParams();
  const volver = rutaSegura(parametros.get("volver"));
  const yo = useYo();
  const entrar = useEntrar();
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [faltan, setFaltan] = useState<{ email?: string; clave?: string }>({});

  if (yo.data) return <Navigate to={volver} replace />;

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    // El botón no se apaga: al tocarlo se dice qué falta, junto al campo
    const falta = {
      email: email.trim() ? undefined : "Escribe tu email.",
      clave: clave ? undefined : "Escribe tu clave.",
    };
    setFaltan(falta);
    if (falta.email || falta.clave) return;
    entrar.mutate({ email: email.trim(), clave });
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col px-4 pt-[max(12vh,env(safe-area-inset-top))] pb-10">
      <div className="mb-6 flex items-center gap-3">
        <img src="/icons/icon-192.png" alt="" className="size-11 rounded-[10px]" />
        <div>
          <h1 className="text-xl leading-7 font-semibold">Monitoreo del hogar</h1>
          <p className="text-sm text-tinta-2">Entra para ver cómo está la casa.</p>
        </div>
      </div>

      <form onSubmit={enviar} noValidate className="placa space-y-4 rounded-[10px] p-4">
        <Campo
          etiqueta="Email"
          type="email"
          inputMode="email"
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="next"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={faltan.email}
        />
        <Campo
          etiqueta="Clave"
          clave
          autoComplete="current-password"
          enterKeyHint="go"
          required
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          error={faltan.clave ?? (entrar.isError ? mensajeDe(entrar.error) : null)}
        />
        <Boton
          type="submit"
          tamano="grande"
          className="w-full"
          ocupado={entrar.isPending && "Entrando…"}
        >
          Entrar
        </Boton>
      </form>

      <p className="mt-4 text-sm text-tinta-3">
        ¿Olvidaste tu clave? Pídele a quien administra el sistema que la restablezca.
      </p>
    </main>
  );
}
