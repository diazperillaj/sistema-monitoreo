"""Invitaciones (§8.2): el admin genera un enlace y lo comparte; quien lo abre crea su cuenta o,
si ya tiene una, se une a la casa. En la base solo queda el hash del token."""

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import Settings
from app.db import Db
from app.schemas.auth import Usuario
from app.schemas.comun import UsuarioBreve, error_api, respuestas_error
from app.schemas.invitaciones import (
    AceptarInvitacion,
    InvitacionCreada,
    InvitacionNueva,
    InvitacionPublica,
    InvitacionVigente,
)
from app.seguridad import exigir, ip_de
from app.services.auth import (
    AccesoAdmin,
    UsuarioActual,
    abrir_sesion,
    ahora,
    hash_token,
    hashear_clave,
    poner_cookie,
    usuario_opcional,
)
from app.services.membresia import avisar, nuevo_evento, texto_union

VIGENCIA = timedelta(hours=72)

router_casa = APIRouter(prefix="/casas/{casa_id}/invitaciones", tags=["invitaciones"])
router_publico = APIRouter(prefix="/invitaciones", tags=["invitaciones"])


def base_de_enlaces(request: Request, settings: Settings) -> str:
    """El origen de la app para armar el enlace. Un POST ya pasó el control de Origin (§12.3),
    así que el origen es uno permitido: en producción, https://<DOMINIO>; en desarrollo,
    localhost, y el enlace funciona igual en el equipo."""
    origen = request.headers.get("origin")
    return origen if origen in settings.origen_permitido else f"https://{settings.dominio}"


# ------------------------------------------------------------------ admin de la casa
@router_casa.post(
    "",
    status_code=201,
    response_model=InvitacionCreada,
    responses=respuestas_error(400, 401, 403, 404),
)
async def crear(
    datos: InvitacionNueva, acceso: AccesoAdmin, request: Request, db: Db
) -> InvitacionCreada:
    """Un enlace de un solo uso, vigente 72 horas, para compartir (por ejemplo, por WhatsApp)."""
    token = secrets.token_urlsafe(32)
    momento = ahora()
    invitacion = models.Invitacion(
        casa_id=acceso.casa_id,
        email=datos.email.lower() if datos.email else None,
        rol=datos.rol,
        token_hash=hash_token(token),
        creada_por=acceso.usuario.id,
        creada_en=momento,
        expira_en=momento + VIGENCIA,
    )
    db.add(invitacion)
    await db.commit()
    base = base_de_enlaces(request, request.app.state.settings)
    return InvitacionCreada(
        id=invitacion.id, url=f"{base}/invitacion/{token}", expira_en=invitacion.expira_en
    )


@router_casa.get(
    "", response_model=list[InvitacionVigente], responses=respuestas_error(401, 403, 404)
)
async def vigentes(acceso: AccesoAdmin, db: Db) -> list[InvitacionVigente]:
    """Las que todavía se pueden usar, de la más nueva a la más vieja."""
    invitacion = models.Invitacion
    filas = await db.execute(
        select(invitacion, models.Usuario.nombre)
        .outerjoin(models.Usuario, models.Usuario.id == invitacion.creada_por)
        .where(
            invitacion.casa_id == acceso.casa_id,
            invitacion.usada_en.is_(None),
            invitacion.expira_en > ahora(),
        )
        .order_by(invitacion.creada_en.desc(), invitacion.id.desc())
    )
    return [
        InvitacionVigente(
            id=fila.id,
            rol=fila.rol,  # type: ignore[arg-type]
            email=fila.email,
            creada_en=fila.creada_en,
            expira_en=fila.expira_en,
            creada_por=(
                UsuarioBreve(id=fila.creada_por, nombre=nombre)
                if fila.creada_por is not None and nombre is not None
                else None
            ),
        )
        for fila, nombre in filas.all()
    ]


@router_casa.delete("/{invitacion_id}", status_code=204, responses=respuestas_error(401, 403, 404))
async def anular(invitacion_id: int, acceso: AccesoAdmin, db: Db) -> None:
    """El enlace deja de servir al instante."""
    resultado = await db.execute(
        delete(models.Invitacion).where(
            models.Invitacion.id == invitacion_id, models.Invitacion.casa_id == acceso.casa_id
        )
    )
    if resultado.rowcount == 0:  # type: ignore[attr-defined]
        raise error_api(404, "no_encontrado", "No existe esa invitación.")
    await db.commit()


# ------------------------------------------------------------------ quien abre el enlace
async def invitacion_valida(
    db: AsyncSession, token: str, momento: datetime, *, bloquear: bool = False
) -> models.Invitacion:
    consulta = select(models.Invitacion).where(models.Invitacion.token_hash == hash_token(token))
    if bloquear:  # dos personas con el mismo enlace a la vez: solo una lo usa
        consulta = consulta.with_for_update()
    invitacion = await db.scalar(consulta)
    if invitacion is None:
        raise error_api(
            404,
            "no_encontrado",
            "Puede que el enlace esté incompleto o que lo hayan anulado. "
            "Pide uno nuevo a quien te invitó.",
        )
    if invitacion.usada_en is not None:
        raise error_api(
            409, "invitacion_usada", "Esta invitación ya se usó. Pide una nueva a quien te invitó."
        )
    if invitacion.expira_en <= momento:
        raise error_api(
            410, "invitacion_vencida", "Esta invitación venció. Pide una nueva a quien te invitó."
        )
    return invitacion


@router_publico.get(
    "/{token}", response_model=InvitacionPublica, responses=respuestas_error(404, 409, 429)
)
async def ver(token: str, request: Request, db: Db) -> InvitacionPublica:
    """A qué casa y con qué rol invita el enlace. Responde 410 si venció."""
    exigir(request.app.state.limites.invitaciones, ip_de(request) or "desconocida")
    invitacion = await invitacion_valida(db, token, ahora())
    casa = await db.get(models.Casa, invitacion.casa_id)
    assert casa is not None  # la invitación se borra con su casa (ON DELETE CASCADE)
    return InvitacionPublica(
        casa_nombre=casa.nombre,
        rol=invitacion.rol,  # type: ignore[arg-type]
        email=invitacion.email,
    )


@router_publico.post(
    "/{token}/aceptar",
    response_model=Usuario,
    responses=respuestas_error(400, 403, 404, 409, 429),
)
async def aceptar(
    token: str, datos: AceptarInvitacion, request: Request, response: Response, db: Db
) -> Usuario:
    """Sin sesión, crea la cuenta con `{nombre, email, clave}`, la une a la casa y entrega la
    cookie. Con sesión, une a la casa a quien ya tiene cuenta (el cuerpo va vacío)."""
    exigir(request.app.state.limites.invitaciones, ip_de(request) or "desconocida")
    settings: Settings = request.app.state.settings
    actual = await usuario_opcional(request, db)
    if actual is not None:
        return await unir(db, request, token, actual)

    if datos.nombre is None or datos.email is None or datos.clave is None:
        faltan = [c for c in ("nombre", "email", "clave") if getattr(datos, c) is None]
        raise HTTPException(
            400,
            {
                "codigo": "solicitud_invalida",
                "mensaje": "Escribe tu nombre, tu email y una clave.",
                "campos": faltan,
            },
        )
    # Antes de tomar el enlace: Argon2 tarda a propósito y la fila queda bloqueada mientras tanto
    clave_hash = await hashear_clave(datos.clave)
    email = datos.email.lower()
    momento = ahora()
    invitacion = await invitacion_valida(db, token, momento, bloquear=True)
    ya_existe = await db.scalar(select(models.Usuario.id).where(models.Usuario.email == email))
    en_uso = error_api(
        409,
        "email_en_uso",
        "Ya hay una cuenta con ese email. Entra con ella y vuelve a abrir este enlace.",
    )
    if ya_existe is not None:
        raise en_uso
    usuario = models.Usuario(
        email=email, nombre=datos.nombre, clave_hash=clave_hash, ultimo_login_en=momento
    )
    db.add(usuario)
    await db.flush()
    db.add(models.Miembro(usuario_id=usuario.id, casa_id=invitacion.casa_id, rol=invitacion.rol))
    evento = nuevo_evento(
        invitacion.casa_id, usuario.id, texto_union(usuario.nombre, invitacion.rol)
    )
    db.add(evento)
    invitacion.usada_en = momento
    invitacion.usada_por = usuario.id
    token_sesion = abrir_sesion(
        db, usuario.id, settings, request.headers.get("user-agent"), ip_de(request)
    )
    try:
        await db.commit()
    except IntegrityError:  # otra persona se registró con ese email en el mismo instante
        raise en_uso from None
    poner_cookie(response, token_sesion, settings)
    await avisar(request.app.state.hub, evento, usuario.nombre)
    return Usuario.model_validate(usuario)


async def unir(db: AsyncSession, request: Request, token: str, actual: UsuarioActual) -> Usuario:
    """Quien ya tiene cuenta se une a la casa. Si ya era miembro, conserva su rol."""
    momento = ahora()
    invitacion = await invitacion_valida(db, token, momento, bloquear=True)
    rol = await db.scalar(
        select(models.Miembro.rol).where(
            models.Miembro.usuario_id == actual.id,
            models.Miembro.casa_id == invitacion.casa_id,
        )
    )
    evento = None
    if rol is None:
        db.add(models.Miembro(usuario_id=actual.id, casa_id=invitacion.casa_id, rol=invitacion.rol))
        evento = nuevo_evento(
            invitacion.casa_id, actual.id, texto_union(actual.nombre, invitacion.rol)
        )
        db.add(evento)
    invitacion.usada_en = momento
    invitacion.usada_por = actual.id
    await db.commit()
    if evento is not None:
        await avisar(request.app.state.hub, evento, actual.nombre)
    return Usuario(
        id=actual.id, email=actual.email, nombre=actual.nombre, es_superadmin=actual.es_superadmin
    )
