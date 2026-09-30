/**
 * Miembros de la casa (§8.2, §8.6, solo admin): quién está y con qué rol, invitar con un enlace
 * de un solo uso y anular los que no se usaron. La casa nunca se queda sin admin: la pantalla lo
 * dice antes de que el servidor lo rechace.
 */
import { ChevronDown, Copy, Share2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import {
  useAnularInvitacion,
  useCambiarRol,
  useCrearInvitacion,
  useInvitaciones,
  useMiembros,
  useQuitarMiembro,
  type InvitacionCreada,
  type MiembroCasa,
  type Rol,
} from "../api/administracion";
import { mensajeDe } from "../api/cliente";
import { useYo } from "../api/consultas";
import { CabeceraAjustes } from "../componentes/CabeceraAjustes";
import { Boton } from "../componentes/ui/Boton";
import { Campo } from "../componentes/ui/Campo";
import { Confirmar } from "../componentes/ui/Confirmar";
import { fecha, hora } from "../dominio/tiempo";
import { cn } from "../lib/utils";
import { useCasaActual } from "../tiempo-real/casaActual";

const NOMBRE_ROL: Record<Rol, string> = { admin: "Admin", cuidador: "Cuidador" };
const QUE_HACE: Record<Rol, string> = {
  cuidador: "Ve el tablero, recibe las alertas y puede silenciarlas.",
  admin: "Además invita a otras personas y cambia los ajustes.",
};

function venceEl(momento: string): string {
  return `vence el ${fecha(momento)} a las ${hora(momento)}`;
}

// ------------------------------------------------------------------ personas
function FilaMiembro({
  casaId,
  miembro,
  soyYo,
  unicoAdmin,
}: {
  casaId: number;
  miembro: MiembroCasa;
  soyYo: boolean;
  unicoAdmin: boolean;
}) {
  const navegar = useNavigate();
  const cambiarRol = useCambiarRol(casaId);
  const quitar = useQuitarMiembro(casaId);
  const [confirmando, setConfirmando] = useState(false);
  const idRol = useId();
  const { usuario } = miembro;

  // Con mutateAsync y no con los callbacks de mutate: al quitar a alguien (o bajarse uno mismo de
  // admin) esta fila desaparece antes de que termine la mutación, y el aviso se perdería con ella
  async function cambiar(rol: Rol) {
    try {
      const cambio = await cambiarRol.mutateAsync({ usuarioId: usuario.id, rol });
      toast.success(`${usuario.nombre} ahora es ${NOMBRE_ROL[cambio.rol].toLowerCase()}`);
    } catch (error) {
      toast.error(mensajeDe(error));
    }
  }

  async function sacar() {
    try {
      await quitar.mutateAsync(usuario.id);
    } catch (error) {
      toast.error(mensajeDe(error));
      return;
    }
    setConfirmando(false);
    if (soyYo) {
      toast.success("Saliste de la casa");
      navegar("/", { replace: true });
    } else {
      toast.success(`${usuario.nombre} ya no es parte de la casa`);
    }
  }

  return (
    <li className="space-y-2 py-3">
      {/* En el celular el rol y el botón bajan juntos a su propia línea en vez de apretar el nombre */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="min-w-0 grow basis-48">
          <p className="font-semibold">
            {usuario.nombre}
            {soyYo && (
              <span className="ml-2 rounded-[4px] bg-cara-2 px-1.5 py-0.5 text-xs font-semibold text-tinta-2 ring-1 ring-filo ring-inset">
                Tú
              </span>
            )}
          </p>
          <p className="truncate text-sm text-tinta-3">{usuario.email}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <label htmlFor={idRol} className="sr-only">
              Rol de {usuario.nombre}
            </label>
            <select
              id={idRol}
              value={miembro.rol}
              disabled={unicoAdmin || cambiarRol.isPending}
              onChange={(e) => void cambiar(e.target.value as Rol)}
              className="h-11 appearance-none rounded-[6px] bg-cara pr-9 pl-3 font-medium ring-1 ring-filo ring-inset disabled:opacity-55"
            >
              <option value="cuidador">Cuidador</option>
              <option value="admin">Admin</option>
            </select>
            <ChevronDown
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-tinta-3"
            />
          </div>
          <Boton
            variante="discreto"
            tamano="compacto"
            disabled={unicoAdmin}
            onClick={() => setConfirmando(true)}
          >
            {soyYo ? "Salir" : "Quitar"}
          </Boton>
        </div>
      </div>
      {unicoAdmin && (
        <p className="text-sm text-tinta-3">
          La casa necesita al menos un admin: haz admin a otra persona para cambiar este rol.
        </p>
      )}
      <Confirmar
        abierto={confirmando}
        alCambiar={setConfirmando}
        titulo={soyYo ? "¿Salir de la casa?" : `¿Quitar a ${usuario.nombre} de la casa?`}
        descripcion={
          soyYo
            ? "Dejarás de ver esta casa y de recibir sus alertas. Para volver, alguien tendrá que invitarte."
            : `Dejará de ver la casa y de recibir sus alertas. Su cuenta y sus otras casas siguen igual.`
        }
        accion={soyYo ? "Salir de la casa" : "Quitar de la casa"}
        ocupado={quitar.isPending && (soyYo ? "Saliendo…" : "Quitando…")}
        alConfirmar={() => void sacar()}
      />
    </li>
  );
}

function Personas({ casaId }: { casaId: number }) {
  const miembros = useMiembros(casaId);
  const yo = useYo().data;
  if (miembros.isPending) {
    return (
      <div
        aria-busy="true"
        aria-label="Cargando los miembros"
        className="placa h-40 rounded-[10px]"
      />
    );
  }
  if (miembros.isError) {
    return (
      <div className="placa space-y-3 rounded-[10px] px-4 py-5">
        <p className="text-tinta-2">{mensajeDe(miembros.error)}</p>
        <Boton variante="secundario" onClick={() => void miembros.refetch()}>
          Reintentar
        </Boton>
      </div>
    );
  }
  const admins = miembros.data.filter((m) => m.rol === "admin").length;
  return (
    <section aria-labelledby="titulo-personas" className="placa rounded-[10px] px-4 pt-4 pb-1">
      <h2 id="titulo-personas" className="font-semibold">
        Personas
      </h2>
      <ul className="divide-y divide-filo">
        {miembros.data.map((miembro) => (
          <FilaMiembro
            key={miembro.usuario.id}
            casaId={casaId}
            miembro={miembro}
            soyYo={miembro.usuario.id === yo?.usuario.id}
            unicoAdmin={miembro.rol === "admin" && admins <= 1}
          />
        ))}
      </ul>
    </section>
  );
}

// ------------------------------------------------------------------ invitar
function EnlaceCreado({
  enlace,
  alTerminar,
}: {
  enlace: InvitacionCreada;
  alTerminar: () => void;
}) {
  const puedeCompartir = typeof navigator.share === "function";
  async function copiar() {
    try {
      await navigator.clipboard.writeText(enlace.url);
      toast.success("Enlace copiado");
    } catch {
      toast.error("No se pudo copiar. Mantén presionado el enlace para copiarlo.");
    }
  }
  async function compartir() {
    try {
      await navigator.share({
        title: "Invitación a Monitoreo del hogar",
        text: "Con este enlace entras a ver la casa y recibir sus alertas:",
        url: enlace.url,
      });
    } catch {
      // Cerró el menú de compartir: no es un error
    }
  }
  return (
    <div className="space-y-3 rounded-[8px] bg-cara-2 p-3 ring-1 ring-filo ring-inset">
      <label className="block space-y-1.5">
        <span className="rotulo">Enlace de invitación</span>
        <input
          readOnly
          value={enlace.url}
          onFocus={(e) => e.currentTarget.select()}
          className="cifras h-11 w-full rounded-[6px] bg-cara px-3 text-sm ring-1 ring-filo ring-inset"
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Boton icono={<Copy aria-hidden="true" className="size-4" />} onClick={() => void copiar()}>
          Copiar enlace
        </Boton>
        {puedeCompartir && (
          <Boton
            variante="secundario"
            icono={<Share2 aria-hidden="true" className="size-4" />}
            onClick={() => void compartir()}
          >
            Compartir
          </Boton>
        )}
      </div>
      <p className="text-sm text-tinta-2">
        Sirve una sola vez y {venceEl(enlace.expira_en)}. Este enlace solo se muestra ahora: cópialo
        o compártelo antes de salir.
      </p>
      <Boton variante="discreto" tamano="compacto" onClick={alTerminar}>
        Crear otro enlace
      </Boton>
    </div>
  );
}

function Invitar({
  casaId,
  enlace,
  setEnlace,
}: {
  casaId: number;
  enlace: InvitacionCreada | null;
  setEnlace: (enlace: InvitacionCreada | null) => void;
}) {
  const crear = useCrearInvitacion(casaId);
  const [rol, setRol] = useState<Rol>("cuidador");
  const [email, setEmail] = useState("");

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    crear.mutate(
      { rol, email: email.trim() || undefined },
      {
        onSuccess: (creada) => {
          setEnlace(creada);
          setEmail("");
        },
        onError: (error) => toast.error(mensajeDe(error)),
      },
    );
  }

  return (
    <section aria-labelledby="titulo-invitar" className="placa space-y-4 rounded-[10px] px-4 py-4">
      <div>
        <h2 id="titulo-invitar" className="font-semibold">
          Invitar a alguien
        </h2>
        <p className="text-sm text-tinta-2">
          Crea un enlace y compártelo, por ejemplo por WhatsApp. Con él, la persona crea su cuenta y
          entra a esta casa.
        </p>
      </div>
      {enlace ? (
        <EnlaceCreado enlace={enlace} alTerminar={() => setEnlace(null)} />
      ) : (
        <form onSubmit={enviar} noValidate className="space-y-4">
          <fieldset className="space-y-2">
            <legend className="mb-1.5 text-sm font-medium">Entra como</legend>
            {(["cuidador", "admin"] as const).map((opcion) => (
              <label
                key={opcion}
                className={cn(
                  "flex cursor-pointer items-start gap-3 rounded-[8px] p-3 ring-1 ring-inset",
                  rol === opcion ? "bg-cara-2 ring-tinta-3" : "ring-filo",
                )}
              >
                <input
                  type="radio"
                  name="rol"
                  value={opcion}
                  checked={rol === opcion}
                  onChange={() => setRol(opcion)}
                  className="mt-1 size-4 accent-tinta"
                />
                <span>
                  <span className="block font-medium">{NOMBRE_ROL[opcion]}</span>
                  <span className="block text-sm text-tinta-2">{QUE_HACE[opcion]}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <Campo
            etiqueta="Email (opcional)"
            type="email"
            inputMode="email"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            ayuda="Solo para que recuerdes a quién se lo mandaste."
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Boton type="submit" ocupado={crear.isPending && "Creando…"}>
            Crear enlace
          </Boton>
        </form>
      )}
    </section>
  );
}

function EnlacesVigentes({
  casaId,
  alAnular,
}: {
  casaId: number;
  alAnular: (invitacionId: number) => void;
}) {
  const invitaciones = useInvitaciones(casaId);
  const anular = useAnularInvitacion(casaId);

  async function anularla(invitacionId: number) {
    try {
      await anular.mutateAsync(invitacionId);
    } catch (error) {
      toast.error(mensajeDe(error));
      return;
    }
    toast.success("Enlace anulado: ya no sirve");
    alAnular(invitacionId);
  }

  if (!invitaciones.data || invitaciones.data.length === 0) return null;
  return (
    <section aria-labelledby="titulo-enlaces" className="placa rounded-[10px] px-4 pt-4 pb-1">
      <h2 id="titulo-enlaces" className="font-semibold">
        Enlaces sin usar
      </h2>
      <ul className="divide-y divide-filo">
        {invitaciones.data.map((invitacion) => (
          <li key={invitacion.id} className="flex items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">
                {NOMBRE_ROL[invitacion.rol]}
                <span className="text-tinta-2"> · {invitacion.email ?? "sin email"}</span>
              </p>
              <p className="text-sm text-tinta-3">
                {venceEl(invitacion.expira_en)}
                {invitacion.creada_por && ` · lo creó ${invitacion.creada_por.nombre}`}
              </p>
            </div>
            <Boton
              variante="discreto"
              tamano="compacto"
              ocupado={anular.isPending && anular.variables === invitacion.id && "Anulando…"}
              onClick={() => void anularla(invitacion.id)}
            >
              Anular
            </Boton>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Miembros() {
  const { casaId } = useCasaActual();
  // El enlace recién creado vive aquí: si lo anulan abajo, la tarjeta de arriba no lo sigue
  // ofreciendo para copiar
  const [enlace, setEnlace] = useState<InvitacionCreada | null>(null);
  if (casaId === null) return null;
  return (
    <>
      <CabeceraAjustes casaId={casaId} />
      <Personas casaId={casaId} />
      <Invitar casaId={casaId} enlace={enlace} setEnlace={setEnlace} />
      <EnlacesVigentes
        casaId={casaId}
        alAnular={(id) => {
          if (enlace?.id === id) setEnlace(null);
        }}
      />
    </>
  );
}
