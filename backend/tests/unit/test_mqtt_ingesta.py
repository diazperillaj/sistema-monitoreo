"""Despacho de los mensajes MQTT según el tópico (§4.2)."""

from typing import Any

import pytest

from app.services.mqtt_ingesta import SUSCRIPCIONES, despachar


class ProcesadorFalso:
    def __init__(self) -> None:
        self.llamadas: list[tuple[Any, ...]] = []

    async def recibir_estado(self, codigo: str, carga: bytes, retenido: bool) -> None:
        self.llamadas.append(("estado", codigo, carga, retenido))

    async def recibir_online(self, codigo: str, carga: bytes, retenido: bool) -> None:
        self.llamadas.append(("online", codigo, carga, retenido))


async def test_estado_y_online_van_a_su_metodo() -> None:
    procesador = ProcesadorFalso()
    await despachar(procesador, "casa/casa-dev/estado", b"{}", False)  # type: ignore[arg-type]
    await despachar(procesador, "casa/casa-dev/online", b"1", True)  # type: ignore[arg-type]
    assert procesador.llamadas == [
        ("estado", "casa-dev", b"{}", False),
        ("online", "casa-dev", b"1", True),
    ]


@pytest.mark.parametrize(
    "topico",
    [
        "casa/casa-dev/cmd",  # lo publica el backend, no la central
        "casa/Casa-Dev/estado",  # ID_CASA solo admite minúsculas, dígitos y guiones
        "casa/abc/estado",  # muy corto
        "casa/casa-dev/estado/extra",
        "otra/casa-dev/estado",
    ],
)
async def test_topicos_ajenos_se_ignoran(topico: str) -> None:
    procesador = ProcesadorFalso()
    await despachar(procesador, topico, b"{}", False)  # type: ignore[arg-type]
    assert procesador.llamadas == []


def test_suscripciones_con_qos_1() -> None:
    assert SUSCRIPCIONES == [("casa/+/estado", 1), ("casa/+/online", 1)]
