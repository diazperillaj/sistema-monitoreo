"""Contrato con la central (§4): espejo de protocolo.h, el payload de estado y los textos.

Los bits y los nombres salen de aquí: ningún otro módulo usa números mágicos (§18).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Alarmas (campo "al")
AL_SIN_MOVIMIENTO = 0x01  # nodos 1, 2, 4
AL_AGUA = 0x02  # nodo 3
AL_GAS = 0x04  # nodo 4
AL_TEMPERATURA = 0x08  # nodo 4
AL_INTRUSION = 0x10  # nodo 0

# Habilitado (campo "hab")
HAB_PRINCIPAL = 0x01
HAB_SECUNDARIO = 0x02  # solo nodo 4 (presencia)

# Flags (campo "fl")
FL_CONTANDO1 = 0x01
FL_CONTANDO2 = 0x02
FL_HORARIO_NOCTURNO = 0x04  # nodo 1 en 22:00–06:00
FL_MADRUGADA = 0x08  # nodo 0 en 00:00–06:00
FL_CALENTANDO = 0x10  # sensor PIR o MQ calentando
FL_ERROR_SENSOR = 0x20  # DS18B20 no responde
FL_HORA_VALIDA = 0x40

NODOS = {0: "Puerta de entrada", 1: "Habitación", 2: "Baño", 3: "Cocina · agua", 4: "Cocina · gas"}
NODO_PUERTA = 0
NODO_HABITACION = 1
NODO_BANO = 2
NODO_COCINA_AGUA = 3
NODO_COCINA_GAS = 4

TipoAlarma = Literal[
    "INTRUSION",
    "SIN_MOVIMIENTO",
    "AGUA",
    "GAS",
    "TEMPERATURA",
    "NODO_SIN_CONEXION",
    "CENTRAL_DESCONECTADA",
]

# Comandos de casa/<ID>/cmd (§4.5) y el verbo con que los anota ejecutarComando()
Accion = Literal["activar", "desactivar", "silenciar"]
VERBOS: dict[str, str] = {"activar": "activó", "desactivar": "desactivó", "silenciar": "silenció"}

# Bit de "al" -> tipo de alarma (§4.4)
ALARMAS_DE_SENSOR: dict[int, TipoAlarma] = {
    AL_INTRUSION: "INTRUSION",
    AL_SIN_MOVIMIENTO: "SIN_MOVIMIENTO",
    AL_AGUA: "AGUA",
    AL_GAS: "GAS",
    AL_TEMPERATURA: "TEMPERATURA",
}


class NodoCentral(BaseModel):
    """Un nodo del payload de estado (§4.3). Los nombres del JSON se conservan en la API."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    id: int = Field(ge=0, le=4)
    nombre: str
    visto: bool  # la central lo oyó al menos una vez desde que arrancó
    en_linea: bool = Field(alias="enLinea")  # último mensaje hace menos de 20 s
    hab: int = Field(ge=0)
    al: int = Field(ge=0)
    mov: int
    fl: int = Field(ge=0)
    c1: int
    l1: int
    c2: int
    l2: int
    v1: float  # nodo 3: caudal (L/min) · nodo 4: temperatura (°C)
    v2: float  # nodo 4: lectura cruda del sensor de gas (0-4095)
    hace: int  # segundos desde su último mensaje

    @property
    def conocido(self) -> bool:
        """Visto y en línea: solo entonces sus alarmas son confiables (§6.4)."""
        return self.visto and self.en_linea


class EventoCentral(BaseModel):
    """Una entrada de la bitácora de la central. No tiene id (§4.3)."""

    model_config = ConfigDict(frozen=True)

    t: str  # "dd/mm HH:MM:SS", o "+<s>s" desde el arranque si aún no hay hora
    x: str
    a: bool  # es una alarma


class EstadoCentral(BaseModel):
    """El payload de casa/<ID>/estado (§4.3)."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    hora: str
    hora_valida: bool = Field(alias="horaValida")
    red: Literal["wifi", "ap"]
    nodos: list[NodoCentral]
    eventos: list[EventoCentral]  # del más reciente al más antiguo, 15 como máximo

    @field_validator("nodos")
    @classmethod
    def cinco_nodos_en_orden(cls, nodos: list[NodoCentral]) -> list[NodoCentral]:
        if [nodo.id for nodo in nodos] != list(NODOS):
            raise ValueError("se esperan los 5 nodos en orden de id")
        return nodos


def parsear_estado(carga: bytes | str) -> EstadoCentral:
    """Valida el JSON de casa/<ID>/estado. Lanza ValueError si no cumple §4.3."""
    return EstadoCentral.model_validate_json(carga)


def sub_valido(nodo_id: int | None, accion: str, sub: int) -> bool:
    """sub = 1 solo existe en el nodo 4 (presencia), para activar o desactivar (§6.5)."""
    return sub == 0 or (nodo_id == NODO_COCINA_GAS and accion in ("activar", "desactivar"))


def nombre_nodo(nodo_id: int | None) -> str:
    return "Central" if nodo_id is None else NODOS[nodo_id]


def limite_de(nodo: NodoCentral, tipo: TipoAlarma) -> int | None:
    """El límite (s) que se guarda al abrir la alarma: el nodo 4 usa l2 para la presencia."""
    if tipo == "SIN_MOVIMIENTO":
        return nodo.l2 if nodo.id == NODO_COCINA_GAS else nodo.l1
    if tipo in ("AGUA", "GAS"):
        return nodo.l1
    return None


def valor_de(nodo: NodoCentral, tipo: TipoAlarma) -> float | None:
    """El valor que se guarda al abrir la alarma: la temperatura en TEMPERATURA."""
    return nodo.v1 if tipo == "TEMPERATURA" else None


def texto_alarma(tipo: str, limite_s: int | None = None, valor: float | None = None) -> str:
    """Texto de una alarma para la app y las notificaciones (§4.4). Minutos enteros, como el firmware."""
    minutos = (limite_s or 0) // 60
    match tipo:
        case "INTRUSION":
            return "Movimiento en la entrada durante la madrugada"
        case "SIN_MOVIMIENTO":
            return f"Sin movimiento por {minutos} min"
        case "AGUA":
            return f"Agua corriendo más de {minutos} min"
        case "GAS":
            return f"Gas detectado por más de {minutos} min"
        case "TEMPERATURA":
            return f"Temperatura alta: {valor or 0:.1f} °C"
        case "NODO_SIN_CONEXION":
            return "Sin conexión con la central"
        case "CENTRAL_DESCONECTADA":
            return "La central no está conectada"
    raise ValueError(f"tipo de alarma desconocido: {tipo}")
