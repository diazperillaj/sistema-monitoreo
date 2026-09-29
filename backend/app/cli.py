"""Comandos de administración (§15.4, §16). En el servidor, dentro del contenedor de la API:

    docker compose exec api python -m app.cli crear-superadmin --email tu@correo.com --nombre "Juan Pablo"
    docker compose exec api python -m app.cli crear-casa --codigo casa-abuela-x7k2 --nombre "Casa de la abuela" --admin tu@correo.com
    docker compose exec api python -m app.cli reset-clave --email persona@correo.com

Y en desarrollo, desde backend/: uv run python -m app.cli exportar-openapi > ../frontend/openapi.json
"""

import argparse
import asyncio
import getpass
import json
import os
import re
import secrets
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models
from app.api.casas import casa_nueva
from app.config import Settings, obtener_settings
from app.db import crear_fabrica, crear_motor
from app.main import create_app
from app.services.auth import hashear_clave

# exportar-openapi no se conecta a la base: la URL solo completa la configuración
URL_SOLO_ESQUEMA = "postgresql+asyncpg://openapi@localhost/openapi"

Sesiones = async_sessionmaker[AsyncSession]


class ErrorCli(Exception):
    """Un error esperado: se muestra el mensaje y el comando termina con código 1."""


async def buscar_usuario(db: AsyncSession, email: str) -> models.Usuario | None:
    return await db.scalar(
        select(models.Usuario).where(models.Usuario.email == email.strip().lower())
    )


async def crear_superadmin(
    sesiones: Sesiones, email: str, nombre: str, clave: str
) -> models.Usuario:
    if len(clave) < 10:
        raise ErrorCli("La clave debe tener al menos 10 caracteres.")
    async with sesiones() as db:
        if await buscar_usuario(db, email):
            raise ErrorCli(f"Ya existe un usuario con el email {email.strip().lower()}.")
        usuario = models.Usuario(
            email=email.strip().lower(),
            nombre=nombre.strip(),
            clave_hash=await hashear_clave(clave),
            es_superadmin=True,
        )
        db.add(usuario)
        await db.commit()
        return usuario


async def crear_casa(
    sesiones: Sesiones, settings: Settings, codigo: str, nombre: str, admin: str | None = None
) -> models.Casa:
    if not re.fullmatch(r"[a-z0-9-]{4,40}", codigo):
        raise ErrorCli(
            "El código debe tener de 4 a 40 minúsculas, números o guiones (es el ID_CASA)."
        )
    async with sesiones() as db:
        if await db.scalar(select(models.Casa.id).where(models.Casa.codigo == codigo)):
            raise ErrorCli(f"Ya existe una casa con el código {codigo}.")
        casa = casa_nueva(codigo, nombre.strip(), settings)
        db.add(casa)
        if admin:
            usuario = await buscar_usuario(db, admin)
            if usuario is None:
                raise ErrorCli(f"No existe un usuario con el email {admin}.")
            await db.flush()
            db.add(models.Miembro(usuario_id=usuario.id, casa_id=casa.id, rol="admin"))
        await db.commit()
        return casa


async def reset_clave(sesiones: Sesiones, email: str) -> str:
    """Pone una clave temporal, cierra todas las sesiones del usuario y devuelve la clave."""
    async with sesiones() as db:
        usuario = await buscar_usuario(db, email)
        if usuario is None:
            raise ErrorCli(f"No existe un usuario con el email {email}.")
        temporal = secrets.token_urlsafe(9)
        usuario.clave_hash = await hashear_clave(temporal)
        await db.execute(delete(models.Sesion).where(models.Sesion.usuario_id == usuario.id))
        await db.commit()
        return temporal


def exportar_openapi() -> str:
    """El contrato de la API para el frontend (§11.7), sin levantar el servidor."""
    settings = Settings(database_url=os.environ.get("DATABASE_URL") or URL_SOLO_ESQUEMA)
    return json.dumps(create_app(settings).openapi(), ensure_ascii=False, indent=2) + "\n"


def pedir_clave() -> str:
    clave = getpass.getpass("Clave (mínimo 10 caracteres): ")
    if clave != getpass.getpass("Repite la clave: "):
        raise ErrorCli("Las claves no coinciden.")
    return clave


async def ejecutar(args: argparse.Namespace) -> None:
    try:
        settings = obtener_settings()
    except ValidationError:
        raise ErrorCli(
            "Falta DATABASE_URL: corre el comando dentro del contenedor de la API."
        ) from None
    motor = crear_motor(settings.database_url)
    sesiones = crear_fabrica(motor)
    try:
        if args.comando == "crear-superadmin":
            usuario = await crear_superadmin(
                sesiones, args.email, args.nombre, args.clave or pedir_clave()
            )
            print(f"Superadmin creado: {usuario.email} (id {usuario.id}).")
        elif args.comando == "crear-casa":
            casa = await crear_casa(sesiones, settings, args.codigo, args.nombre, args.admin)
            print(f"Casa creada: {casa.nombre} (código {casa.codigo}, id {casa.id}).")
            print(
                f"Su central necesita un usuario MQTT: ./scripts/usuario_mqtt.sh {casa.codigo} <clave>"
            )
        elif args.comando == "reset-clave":
            temporal = await reset_clave(sesiones, args.email)
            print(f"Clave temporal: {temporal}")
            print("Se cerraron todas sus sesiones. Que la cambie en Perfil al entrar.")
    finally:
        await motor.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Comandos de administración de Alarma hogar."
    )
    comandos = parser.add_subparsers(dest="comando", required=True, metavar="comando")
    p = comandos.add_parser("crear-superadmin", help="crea un usuario con acceso a todas las casas")
    p.add_argument("--email", required=True)
    p.add_argument("--nombre", required=True)
    p.add_argument("--clave", help="si se omite, se pide sin mostrarla")
    p = comandos.add_parser("crear-casa", help="registra una casa (su central)")
    p.add_argument("--codigo", required=True, help="el ID_CASA de la central")
    p.add_argument("--nombre", required=True)
    p.add_argument("--admin", help="email de un usuario existente que será admin de la casa")
    p = comandos.add_parser("reset-clave", help="pone una clave temporal y cierra sus sesiones")
    p.add_argument("--email", required=True)
    p = comandos.add_parser("exportar-openapi", help="escribe el contrato OpenAPI (§11.7)")
    p.add_argument("--salida", help="archivo de destino; por defecto, la salida estándar")
    args = parser.parse_args(argv)

    # UTF-8 y saltos de línea LF también en Windows, aunque la salida vaya a un archivo
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if args.comando == "exportar-openapi":
        contenido = exportar_openapi()
        if args.salida:
            Path(args.salida).write_text(contenido, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(contenido)
        return 0
    try:
        asyncio.run(ejecutar(args))
    except ErrorCli as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
