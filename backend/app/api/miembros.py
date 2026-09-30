"""Miembros de una casa (§8.6). Los ve cualquier miembro; los cambia el admin. La casa nunca se
queda sin admin: ni se quita ni se baja de rol al último."""

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.db import Db
from app.schemas.comun import error_api, respuestas_error
from app.schemas.miembros import CambioMiembro, MiembroCasa, PersonaMiembro
from app.services.auth import AccesoAdmin, AccesoMiembro
from app.services.membresia import avisar, contar_admins, nuevo_evento, texto_rol, texto_salida

router = APIRouter(prefix="/casas/{casa_id}/miembros", tags=["miembros"])

ULTIMO_ADMIN = "La casa necesita al menos un admin. Haz admin a otra persona primero."


def a_esquema(miembro: models.Miembro, usuario: models.Usuario) -> MiembroCasa:
    return MiembroCasa(
        usuario=PersonaMiembro(id=usuario.id, nombre=usuario.nombre, email=usuario.email),
        rol=miembro.rol,  # type: ignore[arg-type]
        creado_en=miembro.creado_en,
    )


async def bloquear_casa(db: AsyncSession, casa_id: int) -> None:
    """Cambios de membresía de una casa, de a uno: dos admins que se quitan el rol al mismo
    tiempo no dejan la casa sin admin."""
    await db.execute(select(models.Casa.id).where(models.Casa.id == casa_id).with_for_update())


async def buscar(
    db: AsyncSession, casa_id: int, usuario_id: int
) -> tuple[models.Miembro, models.Usuario]:
    fila = (
        await db.execute(
            select(models.Miembro, models.Usuario)
            .join(models.Usuario, models.Usuario.id == models.Miembro.usuario_id)
            .where(models.Miembro.casa_id == casa_id, models.Miembro.usuario_id == usuario_id)
        )
    ).first()
    if fila is None:
        raise error_api(404, "no_encontrado", "Esa persona no es miembro de esta casa.")
    return fila[0], fila[1]


@router.get("", response_model=list[MiembroCasa], responses=respuestas_error(401, 403, 404))
async def listar(acceso: AccesoMiembro, db: Db) -> list[MiembroCasa]:
    """Primero los admins; dentro de cada rol, por nombre."""
    filas = await db.execute(
        select(models.Miembro, models.Usuario)
        .join(models.Usuario, models.Usuario.id == models.Miembro.usuario_id)
        .where(models.Miembro.casa_id == acceso.casa_id)
        .order_by((models.Miembro.rol == "admin").desc(), models.Usuario.nombre, models.Usuario.id)
    )
    return [a_esquema(miembro, usuario) for miembro, usuario in filas.all()]


@router.patch(
    "/{usuario_id}",
    response_model=MiembroCasa,
    responses=respuestas_error(400, 401, 403, 404, 409),
)
async def cambiar_rol(
    usuario_id: int, datos: CambioMiembro, acceso: AccesoAdmin, request: Request, db: Db
) -> MiembroCasa:
    await bloquear_casa(db, acceso.casa_id)
    miembro, usuario = await buscar(db, acceso.casa_id, usuario_id)
    if miembro.rol == datos.rol:
        return a_esquema(miembro, usuario)
    if miembro.rol == "admin" and await contar_admins(db, acceso.casa_id) <= 1:
        raise error_api(409, "ultimo_admin", ULTIMO_ADMIN)
    miembro.rol = datos.rol
    actor = acceso.usuario
    evento = nuevo_evento(
        acceso.casa_id, actor.id, texto_rol(actor.nombre, usuario.nombre, datos.rol)
    )
    db.add(evento)
    await db.commit()
    await avisar(request.app.state.hub, evento, actor.nombre)
    return a_esquema(miembro, usuario)


@router.delete("/{usuario_id}", status_code=204, responses=respuestas_error(401, 403, 404, 409))
async def quitar(usuario_id: int, acceso: AccesoAdmin, request: Request, db: Db) -> None:
    """Deja de ver la casa y de recibir sus alertas. Su cuenta y sus otras casas siguen igual."""
    await bloquear_casa(db, acceso.casa_id)
    miembro, usuario = await buscar(db, acceso.casa_id, usuario_id)
    if miembro.rol == "admin" and await contar_admins(db, acceso.casa_id) <= 1:
        raise error_api(409, "ultimo_admin", ULTIMO_ADMIN)
    actor = acceso.usuario
    await db.delete(miembro)
    texto = texto_salida(actor.nombre, usuario.nombre, misma_persona=actor.id == usuario.id)
    evento = nuevo_evento(acceso.casa_id, actor.id, texto)
    db.add(evento)
    await db.commit()
    await avisar(request.app.state.hub, evento, actor.nombre)
