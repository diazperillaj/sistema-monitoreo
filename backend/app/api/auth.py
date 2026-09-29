"""Autenticación y sesiones (§8.1, §12.1, §12.2)."""

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, select

from app import models
from app.config import Settings
from app.db import Db
from app.schemas.auth import CambioClave, CasaDelUsuario, Login, SesionAbierta, Usuario, Yo
from app.schemas.comun import error_api, respuestas_error
from app.seguridad import exigir, ip_de
from app.services.auth import (
    Actual,
    abrir_sesion,
    ahora,
    borrar_cookie,
    casas_visibles,
    hashear_clave,
    poner_cookie,
    verificar_clave,
)

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post("/login", response_model=Usuario, responses=respuestas_error(400, 401, 403, 429))
async def login(datos: Login, request: Request, response: Response, db: Db) -> models.Usuario:
    """Abre una sesión y la entrega en la cookie `sesion`."""
    email = datos.email.strip().lower()
    ip = ip_de(request) or "desconocida"
    limites = request.app.state.limites
    exigir(limites.login_email, (ip, email))  # 5 por minuto por (IP, email)
    exigir(limites.login_ip, ip)  # 20 por hora por IP
    usuario = await db.scalar(select(models.Usuario).where(models.Usuario.email == email))
    activo = usuario is not None and usuario.activo
    if not await verificar_clave(datos.clave, usuario.clave_hash if activo else None):
        raise error_api(401, "credenciales_invalidas", "Email o clave incorrectos.")
    assert usuario is not None
    settings: Settings = request.app.state.settings
    token = abrir_sesion(
        db, usuario.id, settings, request.headers.get("user-agent"), ip_de(request)
    )
    usuario.ultimo_login_en = ahora()
    await db.commit()
    poner_cookie(response, token, settings)
    return usuario


@router.post("/logout", status_code=204, responses=respuestas_error(401, 403))
async def logout(actual: Actual, request: Request, response: Response, db: Db) -> None:
    """Cierra la sesión actual y borra la cookie."""
    await db.execute(delete(models.Sesion).where(models.Sesion.id == actual.sesion_id))
    await db.commit()
    borrar_cookie(response, request.app.state.settings)


@router.get("/yo", response_model=Yo, responses=respuestas_error(401))
async def yo(actual: Actual, db: Db) -> Yo:
    """El usuario de la sesión y sus casas, con su rol en cada una."""
    casas = await casas_visibles(db, actual)
    return Yo(
        usuario=Usuario(
            id=actual.id,
            email=actual.email,
            nombre=actual.nombre,
            es_superadmin=actual.es_superadmin,
        ),
        casas=[CasaDelUsuario(id=casa.id, nombre=casa.nombre, rol=rol) for casa, rol in casas],
    )


@router.post("/cambiar-clave", status_code=204, responses=respuestas_error(400, 401, 403))
async def cambiar_clave(datos: CambioClave, actual: Actual, db: Db) -> None:
    """Cambia la clave y cierra las demás sesiones del usuario (§12.2)."""
    usuario = await db.get(models.Usuario, actual.id)
    assert usuario is not None
    if not await verificar_clave(datos.clave_actual, usuario.clave_hash):
        # 400 y no 401: la app no debe cerrar la sesión por un error al escribir la clave
        raise error_api(400, "clave_incorrecta", "La clave actual no es correcta.")
    usuario.clave_hash = await hashear_clave(datos.clave_nueva)
    await db.execute(
        delete(models.Sesion).where(
            models.Sesion.usuario_id == actual.id, models.Sesion.id != actual.sesion_id
        )
    )
    await db.commit()


@router.get("/sesiones", response_model=list[SesionAbierta], responses=respuestas_error(401))
async def sesiones(actual: Actual, db: Db) -> list[SesionAbierta]:
    """Las sesiones abiertas del usuario, de la más reciente a la más antigua."""
    filas = await db.scalars(
        select(models.Sesion)
        .where(models.Sesion.usuario_id == actual.id, models.Sesion.expira_en > ahora())
        .order_by(models.Sesion.ultimo_uso_en.desc(), models.Sesion.id.desc())
    )
    return [
        SesionAbierta(
            id=sesion.id,
            user_agent=sesion.user_agent,
            ip=str(sesion.ip) if sesion.ip is not None else None,
            creada_en=sesion.creada_en,
            ultimo_uso_en=sesion.ultimo_uso_en,
            expira_en=sesion.expira_en,
            actual=sesion.id == actual.sesion_id,
        )
        for sesion in filas
    ]


@router.delete("/sesiones/{sesion_id}", status_code=204, responses=respuestas_error(401, 403, 404))
async def cerrar_sesion(
    sesion_id: int, actual: Actual, request: Request, response: Response, db: Db
) -> None:
    """Cierra una de las sesiones del usuario (por ejemplo, la de un celular perdido)."""
    borrada = await db.scalar(
        delete(models.Sesion)
        .where(models.Sesion.id == sesion_id, models.Sesion.usuario_id == actual.id)
        .returning(models.Sesion.id)
    )
    if borrada is None:
        raise error_api(404, "no_encontrado", "No existe esa sesión.")
    await db.commit()
    if sesion_id == actual.sesion_id:
        borrar_cookie(response, request.app.state.settings)
