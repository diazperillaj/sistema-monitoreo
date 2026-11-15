/**
 * Quien abre un enlace de invitación (§8.2, §11.2). Sin sesión: nombre, email y clave crean la
 * cuenta y entra de una. Con sesión: "Unirme" agrega la casa a su cuenta. Un enlace vencido,
 * usado o incompleto lo dice y explica qué hacer.
 */
import { CircleAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import {
  useAceptarInvitacion,
  useInvitacionPublica,
  type InvitacionPublica,
} from "../api/administracion";
import { ErrorApi, mensajeDe } from "../api/cliente";
import { useSalir, useYo, type Yo } from "../api/consultas";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";

const QUE_HACE = {
  cuidador: "Vas a ver el tablero de la casa, recibir sus alertas y poder silenciarlas.",
  admin:
    "Vas a ver el tablero de la casa, recibir sus alertas y poder silenciarlas. Como admin, también puedes invitar a otras personas y cambiar los ajustes.",
};

function Marco({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col px-4 pt-[max(10vh,env(safe-area-inset-top))] pb-10">
      <div className="mb-6 flex items-center gap-3">
        <img src="/icons/icon-192.png" alt="" className="size-11 rounded-[10px]" />
        <p className="text-xl leading-7 font-semibold">Monitoreo del hogar</p>
      </div>
      {children}
    </main>
  );
}

function EnlaceQueNoSirve({ error, volver }: { error: unknown; volver: string }) {
  const vencida = error instanceof ErrorApi && error.estado === 410;
  return (
    <div className="placa space-y-3 rounded-[10px] p-4">
      <h1 className="flex items-start gap-2 text-lg font-semibold">
        <CircleAlert aria-hidden="true" className="mt-1 size-5 shrink-0" />
        {vencida ? "Esta invitación venció" : "Esta invitación no sirve"}
      </h1>
      <p className="text-tinta-2">{mensajeDe(error)}</p>
      <Link
        to={volver}
        className="pulsable inline-flex h-11 items-center rounded-[6px] bg-tinta px-4 font-semibold text-cara"
      >
        Ir a la entrada
      </Link>
    </div>
  );
}

function ConCuenta({
  token,
  invitacion,
  yo,
}: {
  token: string;
  invitacion: InvitacionPublica;
  yo: Yo;
}) {
  const navegar = useNavigate();
  const aceptar = useAceptarInvitacion(token);
  const salir = useSalir();

  async function unirme() {
    try {
      await aceptar.mutateAsync({});
    } catch (error) {
      toast.error(mensajeDe(error));
      return;
    }
    toast.success(`Ya eres parte de ${invitacion.casa_nombre}`);
    navegar("/", { replace: true });
  }

  return (
    <div className="placa space-y-4 rounded-[10px] p-4">
      <p className="text-tinta-2">
        Vas a entrar con tu cuenta,{" "}
        <span className="font-medium text-tinta">{yo.usuario.nombre}</span> ({yo.usuario.email}).
      </p>
      <Boton
        tamano="grande"
        className="w-full"
        ocupado={aceptar.isPending && "Uniéndote…"}
        onClick={() => void unirme()}
      >
        Unirme a la casa
      </Boton>
      <p className="text-sm text-tinta-3">
        ¿No eres tú?{" "}
        <button
          type="button"
          className="font-semibold text-tinta underline underline-offset-4"
          onClick={() => salir.mutate()}
        >
          Salir de esa cuenta
        </button>{" "}
        y crea la tuya.
      </p>
    </div>
  );
}

function SinCuenta({ token, invitacion }: { token: string; invitacion: InvitacionPublica }) {
  const navegar = useNavigate();
  const aceptar = useAceptarInvitacion(token);
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState(invitacion.email ?? "");
  const [clave, setClave] = useState("");
  const [intento, setIntento] = useState(false);

  const faltaNombre = nombre.trim() === "" ? "Escribe tu nombre." : null;
  const faltaEmail = !/^\S+@\S+\.\S+$/.test(email.trim()) ? "Escribe un email válido." : null;
  const faltaClave = clave.length < 10 ? "La clave necesita al menos 10 caracteres." : null;
  const emailEnUso = aceptar.error instanceof ErrorApi && aceptar.error.codigo === "email_en_uso";

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setIntento(true);
    const porCorregir = faltaNombre ? "nombre" : faltaEmail ? "email" : faltaClave ? "clave" : null;
    if (porCorregir) {
      // El foco va al primer campo por corregir: en el celular se abre su teclado
      const campo = evento.currentTarget.elements.namedItem(porCorregir);
      if (campo instanceof HTMLInputElement) campo.focus();
      return;
    }
    try {
      await aceptar.mutateAsync({ nombre: nombre.trim(), email: email.trim(), clave });
    } catch {
      return; // el error se muestra en el formulario (aceptar.error)
    }
    toast.success(`Ya eres parte de ${invitacion.casa_nombre}`, {
      description: "Activa las alertas en este celular desde Perfil.",
    });
    navegar("/", { replace: true });
  }

  return (
    <form onSubmit={enviar} noValidate className="placa space-y-4 rounded-[10px] p-4">
      <Campo
        etiqueta="Tu nombre"
        name="nombre"
        autoComplete="name"
        enterKeyHint="next"
        ayuda="Así te verán las demás personas de la casa."
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        error={intento ? faltaNombre : null}
      />
      <Campo
        etiqueta="Email"
        name="email"
        type="email"
        inputMode="email"
        autoComplete="username"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="next"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={intento ? faltaEmail : null}
      />
      <Campo
        etiqueta="Clave"
        name="clave"
        clave
        autoComplete="new-password"
        enterKeyHint="go"
        ayuda="Mínimo 10 caracteres. Una frase corta es más fácil de recordar."
        value={clave}
        onChange={(e) => setClave(e.target.value)}
        error={intento ? faltaClave : null}
      />
      {aceptar.isError && (
        <p role="alert" className="flex items-start gap-1.5 text-sm font-medium">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>
            {mensajeDe(aceptar.error)}{" "}
            {emailEnUso && (
              <Link
                to={`/login?volver=${encodeURIComponent(`/invitacion/${token}`)}`}
                className="font-semibold underline underline-offset-4"
              >
                Entrar con esa cuenta
              </Link>
            )}
          </span>
        </p>
      )}
      <Boton
        type="submit"
        tamano="grande"
        className="w-full"
        ocupado={aceptar.isPending && "Creando tu cuenta…"}
      >
        Crear cuenta y entrar
      </Boton>
      <p className="text-sm text-tinta-3">
        ¿Ya tienes cuenta?{" "}
        <Link
          to={`/login?volver=${encodeURIComponent(`/invitacion/${token}`)}`}
          className="font-semibold text-tinta underline underline-offset-4"
        >
          Entra con ella
        </Link>{" "}
        y vuelve a abrir este enlace.
      </p>
    </form>
  );
}

export default function Invitacion() {
  const { token = "" } = useParams();
  const yo = useYo();
  const invitacion = useInvitacionPublica(token);
  // Quien llegó sin cuenta sigue viendo su formulario hasta que lo lleve al tablero: al crear la
  // cuenta ya hay sesión, y sin esto se alcanzaría a ver "Unirme a la casa" por un instante
  const [llegoSinCuenta, setLlegoSinCuenta] = useState(false);
  if (!llegoSinCuenta && !yo.isPending && !yo.data) setLlegoSinCuenta(true);

  if (!token) return <Navigate to="/" replace />;
  if (yo.isPending || invitacion.isPending) {
    return (
      <Marco>
        <p aria-busy="true" className="text-tinta-3">
          Abriendo la invitación…
        </p>
      </Marco>
    );
  }
  if (invitacion.isError) {
    return (
      <Marco>
        <EnlaceQueNoSirve error={invitacion.error} volver={yo.data ? "/" : "/login"} />
      </Marco>
    );
  }
  const datos = invitacion.data;
  return (
    <Marco>
      <div className="mb-4 space-y-1">
        <h1 className="text-lg leading-7 font-semibold">Te invitaron a {datos.casa_nombre}</h1>
        <p className="text-tinta-2">{QUE_HACE[datos.rol]}</p>
      </div>
      {yo.data && !llegoSinCuenta ? (
        <ConCuenta token={token} invitacion={datos} yo={yo.data} />
      ) : (
        <SinCuenta token={token} invitacion={datos} />
      )}
    </Marco>
  );
}
