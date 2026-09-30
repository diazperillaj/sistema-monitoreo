"""Lecturas para las gráficas y resumen de alarmas (§7.4, §8.5)."""

from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import func, select

from app import models
from app.db import Db
from app.schemas.comun import respuestas_error
from app.schemas.lecturas import Agregacion, AlarmasDelDia, Metrica, Punto, Resumen
from app.services.auth import AccesoMiembro, ahora

router = APIRouter(prefix="/casas/{casa_id}", tags=["lecturas"])

INTERVALOS = {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "1h": timedelta(hours=1)}
MAX_PUNTOS = 2100  # 24 h cada minuto o 7 días cada 5 minutos: más no cabe en una gráfica
ORIGEN_BIN = datetime(2000, 1, 1, tzinfo=UTC)  # 1h cae en horas exactas también en Bogotá (-05)
ZONA = "America/Bogota"
TIPOS_SENSOR = ("INTRUSION", "SIN_MOVIMIENTO", "AGUA", "GAS", "TEMPERATURA")


def invalida(mensaje: str, campo: str) -> HTTPException:
    return HTTPException(
        400, {"codigo": "solicitud_invalida", "mensaje": mensaje, "campos": [campo]}
    )


@router.get("/lecturas", response_model=list[Punto], responses=respuestas_error(400, 401, 403, 404))
async def lecturas(
    acceso: AccesoMiembro,
    db: Db,
    nodo: Annotated[int, Query(ge=0, le=4)],
    metrica: Metrica,
    desde: Annotated[AwareDatetime, Query(description="medido_en ≥ desde")],
    hasta: Annotated[AwareDatetime, Query(description="medido_en < hasta")],
    agregacion: Agregacion = "5m",
) -> list[Punto]:
    """Promedio por intervalo, del más viejo al más nuevo. Los intervalos sin lecturas (nodo
    apagado, central caída) no aparecen: la gráfica muestra el hueco en vez de inventarlo."""
    if hasta <= desde:
        raise invalida("`hasta` debe ser posterior a `desde`.", "hasta")
    intervalo = INTERVALOS[agregacion]
    if (hasta - desde) / intervalo > MAX_PUNTOS:
        raise invalida(
            "Son demasiados puntos: pide un intervalo más largo o un periodo más corto.",
            "agregacion",
        )
    lectura = models.Lectura
    t = func.date_bin(intervalo, lectura.medido_en, ORIGEN_BIN).label("t")
    filas = await db.execute(
        select(t, func.avg(lectura.valor))
        .where(
            lectura.casa_id == acceso.casa_id,
            lectura.nodo_id == nodo,
            lectura.metrica == metrica,
            lectura.medido_en >= desde,
            lectura.medido_en < hasta,
        )
        .group_by(t)
        .order_by(t)
    )
    return [Punto(t=momento, valor=round(float(valor), 2)) for momento, valor in filas.all()]


@router.get("/resumen", response_model=Resumen, responses=respuestas_error(400, 401, 403, 404))
async def resumen(
    acceso: AccesoMiembro, db: Db, dias: Annotated[int, Query(ge=1, le=90)] = 7
) -> Resumen:
    """Las alarmas de los últimos `dias` días (hoy incluido, con la hora de Bogotá)."""
    zona = ZoneInfo(ZONA)
    hoy = ahora().astimezone(zona).date()
    primer_dia = hoy - timedelta(days=dias - 1)
    desde = datetime.combine(primer_dia, time(0), tzinfo=zona)
    alarma = models.Alarma
    en_periodo = (alarma.casa_id == acceso.casa_id) & (alarma.inicio_en >= desde)

    por_tipo = await db.execute(
        select(alarma.tipo, func.count()).where(en_periodo).group_by(alarma.tipo)
    )
    # Tiempo de respuesta = fin_en - inicio_en de las que silenció una persona (§8.5)
    medio = await db.scalar(
        select(func.avg(func.extract("epoch", alarma.fin_en - alarma.inicio_en))).where(
            en_periodo, alarma.cerrada_por == "usuario"
        )
    )
    dia = func.date(func.timezone(ZONA, alarma.inicio_en))
    es_sensor = alarma.tipo.in_(TIPOS_SENSOR)
    por_dia = await db.execute(
        select(dia, es_sensor, func.count()).where(en_periodo).group_by(dia, es_sensor)
    )
    cuentas: dict[tuple[object, bool], int] = {
        (fecha, sensor): cantidad for fecha, sensor, cantidad in por_dia.all()
    }
    dias_del_periodo = [primer_dia + timedelta(days=i) for i in range(dias)]
    return Resumen(
        dias=dias,
        alarmas_por_tipo={tipo: cantidad for tipo, cantidad in por_tipo.all()},
        tiempo_medio_respuesta_s=round(float(medio), 1) if medio is not None else None,
        alarmas_por_dia=[
            AlarmasDelDia(
                dia=fecha,
                sensor=cuentas.get((fecha, True), 0),
                conexion=cuentas.get((fecha, False), 0),
            )
            for fecha in dias_del_periodo
        ],
    )
