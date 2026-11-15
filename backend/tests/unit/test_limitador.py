"""Cubeta de fichas de los límites de intentos (§12.4)."""

import pytest

from app.seguridad import Limitador


def test_permite_hasta_la_capacidad_y_despues_pide_esperar() -> None:
    limitador = Limitador(capacidad=5, por_segundo=5 / 60)  # 5 por minuto
    assert [limitador.tomar("ana", ahora=0.0) for _ in range(5)] == [0.0] * 5
    assert limitador.tomar("ana", ahora=0.0) == pytest.approx(12)  # una ficha cada 12 s


def test_las_fichas_se_recargan_con_el_tiempo() -> None:
    limitador = Limitador(capacidad=5, por_segundo=5 / 60)
    for _ in range(5):
        limitador.tomar("ana", ahora=0.0)
    assert limitador.tomar("ana", ahora=6.0) == pytest.approx(6)
    assert limitador.tomar("ana", ahora=12.0) == 0


def test_cada_clave_tiene_su_propia_cubeta() -> None:
    limitador = Limitador(capacidad=1, por_segundo=1)
    assert limitador.tomar(("1.2.3.4", "ana@ejemplo.com"), ahora=0.0) == 0
    assert limitador.tomar(("1.2.3.4", "ana@ejemplo.com"), ahora=0.0) > 0
    assert limitador.tomar(("1.2.3.4", "beto@ejemplo.com"), ahora=0.0) == 0


def test_podar_olvida_solo_las_cubetas_que_ya_se_llenaron() -> None:
    limitador = Limitador(capacidad=2, por_segundo=1)
    limitador.tomar("llena", ahora=0.0)
    limitador.tomar("gastada", ahora=9.0)
    limitador.tomar("gastada", ahora=9.0)
    limitador.podar(ahora=10.0)
    assert limitador.tomar("gastada", ahora=10.0) == 0  # le quedaba una ficha
    assert limitador.tomar("gastada", ahora=10.0) > 0  # no se olvidó: seguía gastada
