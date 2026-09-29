"""Claves, sesiones y dependencias de permisos (§12.1, §12.2, §12.5)."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.config import Settings
from app.db import Db
from app.schemas.comun import error_api

COOKIE = "sesion"
RENOVAR_TRAS = timedelta(days=1)

_hasher = PasswordHash.recommended()  # Argon2id con los parámetros por defecto de pwdlib


@lru_cache
def _hash_ficticio() -> str:
    return _hasher.hash("clave ficticia para igualar tiempos")


async def hashear_clave(clave: str) -> str:
    # En un hilo: Argon2 tarda a propósito, y el único worker también atiende MQTT
    return await run_in_threadpool(_hasher.hash, clave)


async def verificar_clave(clave: str, clave_hash: str | None) -> bool:
    """Sin hash (usuario inexistente o inactivo) verifica contra uno ficticio: tarda lo mismo
    y no revela si el email existe (§12.1)."""
    valida = await run_in_threadpool(_hasher.verify, clave, clave_hash or _hash_ficticio())
    return valida and clave_hash is not None


def ahora() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def abrir_sesion(
    db: AsyncSession, usuario_id: int, settings: Settings, user_agent: str | None, ip: str | None
) -> str:
    """Agrega la sesión a `db` (sin commit) y devuelve el token para la cookie."""
    token = secrets.token_urlsafe(32)
    momento = ahora()
    db.add(
        models.Sesion(
            usuario_id=usuario_id,
            token_hash=hash_token(token),  # en la base solo va el hash (§12.2)
            creada_en=momento,
            ultimo_uso_en=momento,
            expira_en=momento + timedelta(days=settings.sesion_dias),
            user_agent=user_agent[:300] if user_agent else None,
            ip=ip,
        )
    )
    return token


def poner_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.sesion_dias * 86400,
        path="/",
        httponly=True,
        secure=settings.cookie_segura,
        samesite="lax",
    )


def borrar_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        COOKIE, path="/", httponly=True, secure=settings.cookie_segura, samesite="lax"
    )


@dataclass(frozen=True)
class UsuarioActual:
    id: int
    email: str
    nombre: str
    es_superadmin: bool
    sesion_id: int


@dataclass(frozen=True)
class AccesoCasa:
    usuario: UsuarioActual
    casa_id: int
    rol: str  # rol efectivo: el superadmin cuenta como admin en todas las casas


async def buscar_sesion(
    db: AsyncSession, token: str, momento: datetime
) -> tuple[models.Sesion, models.Usuario] | None:
    """La sesión vigente de ese token y su usuario, si sigue activo. La usan la API y el WS."""
    fila = (
        await db.execute(
            select(models.Sesion, models.Usuario)
            .join(models.Usuario, models.Usuario.id == models.Sesion.usuario_id)
            .where(
                models.Sesion.token_hash == hash_token(token),
                models.Sesion.expira_en > momento,
                models.Usuario.activo,
            )
        )
    ).first()
    return (fila[0], fila[1]) if fila else None


def a_usuario_actual(sesion: models.Sesion, usuario: models.Usuario) -> UsuarioActual:
    return UsuarioActual(
        usuario.id, usuario.email, usuario.nombre, usuario.es_superadmin, sesion.id
    )


async def usuario_actual(request: Request, response: Response, db: Db) -> UsuarioActual:
    token = request.cookies.get(COOKIE)
    if not token:
        raise error_api(401, "no_autenticado", "Inicia sesión para continuar.")
    momento = ahora()
    encontrada = await buscar_sesion(db, token, momento)
    if encontrada is None:
        raise error_api(401, "no_autenticado", "La sesión venció. Inicia sesión de nuevo.")
    sesion, usuario = encontrada
    settings: Settings = request.app.state.settings
    if momento - sesion.ultimo_uso_en > RENOVAR_TRAS:  # renovación deslizante (§12.2)
        sesion.ultimo_uso_en = momento
        sesion.expira_en = momento + timedelta(days=settings.sesion_dias)
        await db.commit()
        poner_cookie(response, token, settings)
    return a_usuario_actual(sesion, usuario)


Actual = Annotated[UsuarioActual, Depends(usuario_actual)]


async def rol_en_casa(db: AsyncSession, usuario: UsuarioActual, casa_id: int) -> str | None:
    """El rol efectivo del usuario en la casa, o None si no es miembro (o la casa no existe).
    El superadmin cuenta como admin en todas las casas."""
    rol = await db.scalar(
        select(models.Miembro.rol).where(
            models.Miembro.usuario_id == usuario.id, models.Miembro.casa_id == casa_id
        )
    )
    if rol is None and usuario.es_superadmin and await db.get(models.Casa, casa_id) is not None:
        return "admin"
    return rol


async def requiere_miembro(casa_id: int, usuario: Actual, db: Db) -> AccesoCasa:
    rol = await rol_en_casa(db, usuario, casa_id)
    if rol is None:
        if usuario.es_superadmin:
            raise error_api(404, "no_encontrado", "No existe esa casa.")
        # También si la casa no existe: a quien no es miembro no se le confirma su existencia
        raise error_api(403, "sin_permiso", "No tienes acceso a esta casa.")
    return AccesoCasa(usuario, casa_id, rol)


AccesoMiembro = Annotated[AccesoCasa, Depends(requiere_miembro)]


async def requiere_admin(acceso: AccesoMiembro) -> AccesoCasa:
    if acceso.rol != "admin":
        raise error_api(403, "sin_permiso", "Solo un admin de la casa puede hacer esto.")
    return acceso


AccesoAdmin = Annotated[AccesoCasa, Depends(requiere_admin)]


async def requiere_superadmin(usuario: Actual) -> UsuarioActual:
    if not usuario.es_superadmin:
        raise error_api(403, "sin_permiso", "Solo el superadmin puede hacer esto.")
    return usuario


Superadmin = Annotated[UsuarioActual, Depends(requiere_superadmin)]


async def casas_visibles(db: AsyncSession, usuario: UsuarioActual) -> list[tuple[models.Casa, str]]:
    """Las casas del usuario con su rol efectivo, por nombre. El superadmin las ve todas."""
    consulta = select(models.Casa, models.Miembro.rol).order_by(models.Casa.nombre, models.Casa.id)
    miembro_de = (models.Miembro.casa_id == models.Casa.id) & (
        models.Miembro.usuario_id == usuario.id
    )
    if usuario.es_superadmin:
        consulta = consulta.outerjoin(models.Miembro, miembro_de)
    else:
        consulta = consulta.join(models.Miembro, miembro_de)
    return [(casa, rol or "admin") for casa, rol in (await db.execute(consulta)).all()]
