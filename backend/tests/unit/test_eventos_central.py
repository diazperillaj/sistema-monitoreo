"""Eventos nuevos de la bitácora de la central (§6.4, §13.1)."""

import pytest

from app.protocolo import EventoCentral
from app.services.eventos_central import eventos_nuevos, se_importa


def ev(t: str, x: str) -> EventoCentral:
    return EventoCentral(t=t, x=x, a=False)


A = ev("27/09 13:00:00", "App (casa): activó Baño")
B = ev("27/09 13:05:00", "App (casa): silenció Baño")
C = ev("27/09 13:10:00", "Botón de la central: silenció todas las alarmas")
D = ev("27/09 13:15:00", "App (casa): desactivó Habitación")


def test_los_nuevos_estan_al_principio() -> None:
    assert eventos_nuevos([B, A], [D, C, B, A]) == [D, C]


def test_la_ventana_de_15_eventos_se_corre() -> None:
    assert eventos_nuevos([B, A, ev("27/09 12:00:00", "viejo")], [C, B, A]) == [C]


def test_sin_estado_anterior_toda_la_lista_es_nueva() -> None:
    assert eventos_nuevos(None, [B, A]) == [B, A]
    assert eventos_nuevos([], [B, A]) == [B, A]


def test_una_reconexion_sin_reinicio_no_duplica() -> None:
    assert eventos_nuevos([B, A], [B, A]) == []
    assert eventos_nuevos([C, B, A], [D, C, B, A]) == [D]


def test_un_reinicio_que_repite_central_iniciada_se_importa() -> None:
    iniciada = ev("+4s", "Central iniciada")
    antes_del_corte = [B, A, iniciada]  # la bitácora del arranque anterior
    despues = [ev("+5s", "Baño conectado"), iniciada]  # arranca de cero con el mismo "+4s"
    assert eventos_nuevos(antes_del_corte, despues) == despues


def test_el_tramo_comun_tiene_que_coincidir_entero() -> None:
    otro = ev("27/09 12:00:00", "otro")
    assert eventos_nuevos([B, A], [B, otro]) == [B, otro]


def test_limite_conocido_lista_identica_tras_un_reinicio() -> None:
    """Sin nada entre dos reinicios y con los mismos segundos, no se distinguen (§6.4)."""
    arranque = [ev("+5s", "Baño conectado"), ev("+4s", "Central iniciada")]
    assert eventos_nuevos(arranque, list(arranque)) == []


@pytest.mark.parametrize(
    ("texto", "importa"),
    [
        ("Central iniciada", True),
        ("App (casa): silenció Baño", True),
        ("Botón de la central: silenció todas las alarmas", True),
        ("Hora ajustada desde la app", True),
        ("ALARMA Baño: sin movimiento por 10 min", False),
        ("App remota: silenció Baño", False),
        ("Baño conectado", False),
        ("Baño reconectado", False),
        ("Cocina · gas perdió la conexión", False),
    ],
)
def test_que_eventos_se_importan(texto: str, importa: bool) -> None:
    assert se_importa(ev("+1s", texto)) is importa
