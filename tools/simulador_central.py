"""Simulador de la central de alarmas (§13.3).

Se conecta al broker como una central ESP32 real y reproduce su comportamiento:

- mismo client ID, keep-alive y LWT que atenderMqtt() del firmware (§4.1);
- publica casa/<ID>/estado cada 5 s, y al instante si cambian las alarmas, el habilitado,
  la conexión de los nodos o la bitácora, con el formato de jsonEstado() (§4.3);
- aplica los comandos de casa/<ID>/cmd igual que procesarComandoRemoto() (§4.5).

Uso, desde backend/ (usa su entorno):

    uv run python ../tools/simulador_central.py --casa casa-dev --clave <clave>

Con TLS, como una central real (en desarrollo el certificado es para "localhost"):

    uv run python ../tools/simulador_central.py --casa casa-dev --clave <clave> --puerto 8883 --tls --ca ../mosquitto/certs/ca.crt

Escribe "ayuda" para ver el menú. Las órdenes también pueden llegar por una tubería, una por
línea, para guionar un escenario ("w <s>" espera). Al acabarse, la central sigue publicando:

    printf 'w 8
a 2
w 10
s 2
' | uv run python ../tools/simulador_central.py --casa casa-dev
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import ssl
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

# Mismos valores que protocolo.h y los sketches de cada nodo (§1.1, §4.4)
AL_SIN_MOVIMIENTO = 0x01
AL_AGUA = 0x02
AL_GAS = 0x04
AL_TEMPERATURA = 0x08
AL_INTRUSION = 0x10
HAB_PRINCIPAL = 0x01
HAB_SECUNDARIO = 0x02
FL_CONTANDO1 = 0x01
FL_CONTANDO2 = 0x02
FL_HORARIO_NOCTURNO = 0x04
FL_MADRUGADA = 0x08
FL_CALENTANDO = 0x10
FL_HORA_VALIDA = 0x40

NOMBRES = ("Puerta de entrada", "Habitación", "Baño", "Cocina · agua", "Cocina · gas")
LIMITE_HABITACION_S = 30 * 60
LIMITE_BANO_S = 10 * 60
LIMITE_AGUA_S = 8 * 60
LIMITE_GAS_S = 4 * 60
LIMITE_PRESENCIA_S = 20 * 60
TEMPERATURA_NORMAL = 24.6
TEMPERATURA_MAXIMA = 56.0
GRACIA_TEMPERATURA_S = 120
CALENTAMIENTO_PIR_S = 60
CALENTAMIENTO_MQ_S = 120
NODO_SIN_CONEXION_S = 20
INTERVALO_PUBLICACION_S = 5
MAX_EVENTOS = 30
EVENTOS_PUBLICADOS = 15
RETARDO_ESPNOW_S = 0.3
SEGUNDOS_WIFI = 4  # lo que tarda la central en conectarse al WiFi antes de terminar setup()
ZONA = timezone(timedelta(hours=-5))  # ZONA_HORARIA del firmware: Colombia, sin horario de verano

TIPOS_ALARMA = {
    "intrusion": AL_INTRUSION,
    "sin_movimiento": AL_SIN_MOVIMIENTO,
    "agua": AL_AGUA,
    "gas": AL_GAS,
    "temperatura": AL_TEMPERATURA,
}
TIPOS_POR_NODO = {
    0: ("intrusion",),
    1: ("sin_movimiento",),
    2: ("sin_movimiento",),
    3: ("agua",),
    4: ("gas", "temperatura", "sin_movimiento"),
}
VERBOS = {"activar": "activó", "desactivar": "desactivó", "silenciar": "silenció"}

AYUDA = """\
Comandos:
  a <nodo> [tipo]  dispara una alarma (tipos: intrusion, sin_movimiento, agua, gas, temperatura)
  s <nodo>         silencia con el botón del propio nodo
  b                botón BOOT de la central: silencia todas las alarmas
  m <nodo>         movimiento (en el nodo 3 abre o cierra la llave del agua)
  ok <nodo>        normaliza el nodo: sin gas, temperatura normal, llave cerrada
  x <nodo>         apaga o enciende un nodo (1 a 4)
  n                cambia el horario nocturno de la habitación (22:00 / 06:00)
  r                reinicia la central (bitácora nueva y nodos sin ver unos segundos)
  c                corta la conexión sin DISCONNECT (el broker publica el LWT); otra vez: reconecta
  e                muestra el estado que se publica
  w <segundos>     espera (para guiones que llegan por una tubería)
  q                sale como un corte de luz (el broker publica el LWT)"""


def atoi(texto: str) -> int:
    """Como atoi() de C: el número del principio del texto, o 0."""
    coincidencia = re.match(r"\s*([+-]?\d+)", texto)
    return int(coincidencia.group(1)) if coincidencia else 0


@dataclass
class Nodo:
    """Estado interno de un nodo, como lo lleva su propio sketch."""

    id: int
    encendido: bool = True
    arranque: float = 0.0
    hab: int = HAB_PRINCIPAL
    al: int = 0
    ultimo_mov: float = 0.0
    mov_hasta: float = 0.0
    contando: bool = False  # baño: alguien entró · cocina agua: hay flujo
    inicio: float = 0.0  # agua y gas: inicio del conteo
    gas: bool = False
    temperatura: float = TEMPERATURA_NORMAL
    ultimo_silencio: float | None = None

    def __post_init__(self) -> None:
        if self.id == 4:
            self.hab = HAB_PRINCIPAL | HAB_SECUNDARIO

    def encender(self, ahora: float) -> None:
        """Al arrancar, el nodo pierde lo que tenía en RAM; "hab" sigue en sus Preferences."""
        self.encendido = True
        self.arranque = ahora
        self.al = 0
        self.ultimo_mov = self.inicio = ahora
        self.contando = False
        self.gas = False

    def movimiento(self, ahora: float) -> None:
        if self.id == 3:  # en la cocina · agua, el "movimiento" es el flujo
            if self.contando:
                self.cerrar_llave()
            else:
                self.contando, self.inicio = True, ahora
            return
        self.ultimo_mov = ahora
        self.mov_hasta = ahora + 3
        if self.id == 2 and self.hab and not self.contando:
            self.contando = True  # alguien entró al baño

    def cerrar_llave(self) -> None:
        self.contando = False
        self.al &= ~AL_AGUA  # FLUJO_CERRADO_APAGA_ALARMA

    def normalizar(self) -> None:
        self.gas = False
        self.temperatura = TEMPERATURA_NORMAL
        if self.id == 3 and self.contando:
            self.cerrar_llave()

    def disparar(self, tipo: str, ahora: float) -> str | None:
        """Lleva el nodo a la condición de alarma. Devuelve el motivo si no se puede."""
        if tipo not in TIPOS_POR_NODO[self.id]:
            return f"el nodo {self.id} no tiene alarma de tipo {tipo}"
        necesario = HAB_SECUNDARIO if self.id == 4 and tipo == "sin_movimiento" else HAB_PRINCIPAL
        if not self.hab & necesario:
            return "esa vigilancia está desactivada"
        if tipo == "sin_movimiento":
            self.ultimo_mov = (
                ahora - {1: LIMITE_HABITACION_S, 2: LIMITE_BANO_S, 4: LIMITE_PRESENCIA_S}[self.id]
            )
            self.contando = False  # el baño deja de contar al disparar
        elif tipo == "agua":
            self.contando, self.inicio = True, ahora - LIMITE_AGUA_S
        elif tipo == "gas":
            self.gas, self.inicio = True, ahora - LIMITE_GAS_S
        elif tipo == "temperatura":
            self.temperatura = 60.0
        self.al |= TIPOS_ALARMA[tipo]
        return None

    def comando(self, accion: str, sub: int, ahora: float) -> None:
        """aplicarComando() de cada sketch."""
        if accion == "silenciar":
            self.al = 0
            self.ultimo_mov = self.inicio = ahora
            if self.id == 2:
                self.contando = False
            if self.id == 4:
                self.ultimo_silencio = ahora
            return
        activar = accion == "activar"
        if self.id == 4:  # sub 0: gas y temperatura · sub 1: presencia
            bit = HAB_SECUNDARIO if sub == 1 else HAB_PRINCIPAL
            if activar:
                self.hab |= bit
                self.ultimo_mov = ahora
            else:
                self.hab &= ~bit
                self.al &= ~(AL_SIN_MOVIMIENTO if sub == 1 else AL_GAS | AL_TEMPERATURA)
            return
        self.hab = HAB_PRINCIPAL if activar else 0
        if not activar:
            self.al = 0
        self.ultimo_mov = self.inicio = ahora
        if self.id == 2:
            self.contando = False

    def revisar(self, ahora: float) -> None:
        """Alarmas por tiempo, como el loop() de cada sketch."""
        if self.id == 1:
            if (
                self.hab
                and not self.al & AL_SIN_MOVIMIENTO
                and ahora - self.ultimo_mov >= LIMITE_HABITACION_S
            ):
                self.al |= AL_SIN_MOVIMIENTO
        elif self.id == 2:
            if (
                self.hab
                and self.contando
                and not self.al & AL_SIN_MOVIMIENTO
                and ahora - self.ultimo_mov >= LIMITE_BANO_S
            ):
                self.al |= AL_SIN_MOVIMIENTO
                self.contando = False
        elif self.id == 3:
            if (
                self.hab
                and self.contando
                and not self.al & AL_AGUA
                and ahora - self.inicio >= LIMITE_AGUA_S
            ):
                self.al |= AL_AGUA
        elif self.id == 4:
            vigila_gas = bool(self.hab & HAB_PRINCIPAL)
            if (
                vigila_gas
                and self.gas
                and not self.al & AL_GAS
                and ahora - self.inicio >= LIMITE_GAS_S
            ):
                self.al |= AL_GAS
            en_gracia = (
                self.ultimo_silencio is not None
                and ahora - self.ultimo_silencio < GRACIA_TEMPERATURA_S
            )
            if (
                vigila_gas
                and self.temperatura > TEMPERATURA_MAXIMA
                and not self.al & AL_TEMPERATURA
                and not en_gracia
            ):
                self.al |= AL_TEMPERATURA
            if (
                self.hab & HAB_SECUNDARIO
                and not self.al & AL_SIN_MOVIMIENTO
                and ahora - self.ultimo_mov >= LIMITE_PRESENCIA_S
            ):
                self.al |= AL_SIN_MOVIMIENTO

    def mensaje(self, ahora: float, hora_valida: bool, noche: bool) -> dict[str, float]:
        """Lo que el nodo manda por ESP-NOW: llenarEstado() de cada sketch."""
        m = dict.fromkeys(("fl", "c1", "l1", "c2", "l2", "v1", "v2"), 0.0)
        m.update(hab=self.hab, al=self.al, mov=int(ahora < self.mov_hasta))
        fl = FL_HORA_VALIDA if hora_valida else 0
        encendido_hace = ahora - self.arranque
        if self.id in (0, 1, 2) and encendido_hace < CALENTAMIENTO_PIR_S:
            fl |= FL_CALENTANDO
        if self.id == 0:
            if hora_valida and datetime.now(ZONA).hour < 6:
                fl |= FL_MADRUGADA
        elif self.id == 1:
            m["l1"] = LIMITE_HABITACION_S
            if self.hab:
                fl |= FL_CONTANDO1
                m["c1"] = int(ahora - self.ultimo_mov)
            if hora_valida and noche:
                fl |= FL_HORARIO_NOCTURNO
        elif self.id == 2:
            m["l1"] = LIMITE_BANO_S
            if self.contando:
                fl |= FL_CONTANDO1
                m["c1"] = int(ahora - self.ultimo_mov)
        elif self.id == 3:
            m["mov"] = int(self.contando)
            m["l1"] = LIMITE_AGUA_S
            m["v1"] = 6.4 if self.contando else 0.0
            if self.contando and self.hab:
                fl |= FL_CONTANDO1
                m["c1"] = int(ahora - self.inicio)
        else:
            m["l1"], m["l2"] = LIMITE_GAS_S, LIMITE_PRESENCIA_S
            m["v1"] = self.temperatura
            m["v2"] = 1950 if self.gas else 640
            if self.hab & HAB_PRINCIPAL and self.gas:
                fl |= FL_CONTANDO1
                m["c1"] = int(ahora - self.inicio)
            if self.hab & HAB_SECUNDARIO:
                fl |= FL_CONTANDO2
                m["c2"] = int(ahora - self.ultimo_mov)
            if encendido_hace < CALENTAMIENTO_MQ_S:
                fl |= FL_CALENTANDO
        m["fl"] = fl
        return m


@dataclass
class VistaNodo:
    """Lo que la central sabe de un nodo (struct Nodo del gateway)."""

    visto: bool = False
    en_linea: bool = False
    ultimo: float = 0.0
    primer_reporte: float = 0.0
    est: dict[str, float] = field(default_factory=dict)


class Central:
    """La central: nodo 0 (puerta), bitácora y cliente MQTT, como gateway_puerta.ino."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.RLock()
        self.detener = threading.Event()
        ahora = time.monotonic()
        self.nodos = [Nodo(i) for i in range(5)]
        for nodo in self.nodos:
            nodo.encender(ahora)
        hora = datetime.now(ZONA).hour
        self.noche = hora >= 22 or hora < 6
        if self.noche:
            self.nodos[1].hab = 0  # la habitación arranca en pausa si es de noche
        self.nodos_con_hora = False
        self.conectado = False
        self.firma_anterior: tuple | None = None
        self.ultima_publicacion = 0.0
        base = f"casa/{args.casa}"
        self.topico_estado = f"{base}/estado"
        self.topico_online = f"{base}/online"
        self.topico_cmd = f"{base}/cmd"
        self.arrancar(ahora)
        self.cliente = self._crear_cliente()

    # ---------------------------------------------------------------- central
    def arrancar(self, ahora: float) -> None:
        """Arranque de la central: bitácora vacía y sin hora hasta que responda el NTP."""
        self.arranque = ahora - SEGUNDOS_WIFI
        self.hora_valida_desde = ahora + self.args.sin_hora
        self.eventos: list[dict[str, object]] = []
        self.total_eventos = 0
        self.vistas = [VistaNodo() for _ in range(5)]
        for vista in self.vistas[1:]:
            vista.primer_reporte = ahora + random.uniform(0.5, 3.0)  # los nodos reportan cada 3 s
        self.nodos[0].encender(ahora)  # la puerta es la propia central
        self.registrar_evento("Central iniciada")

    def hora_valida(self, ahora: float) -> bool:
        return ahora >= self.hora_valida_desde

    def texto_hora(self, ahora: float, formato: str) -> str:
        if self.hora_valida(ahora):
            return datetime.now(ZONA).strftime(formato)
        return f"+{int(ahora - self.arranque)}s"

    def registrar_evento(self, texto: str, alarma: bool = False) -> None:
        t = self.texto_hora(time.monotonic(), "%d/%m %H:%M:%S")
        self.eventos.append({"t": t, "x": texto, "a": alarma})
        del self.eventos[:-MAX_EVENTOS]
        self.total_eventos += 1
        print(f"[evento] {t}  {texto}")

    def revisar_alarmas_nuevas(self, i: int, antes: int, m: dict[str, float]) -> None:
        nuevas = int(m["al"]) & ~antes
        nombre = NOMBRES[i]
        if nuevas & AL_INTRUSION:
            self.registrar_evento(f"ALARMA {nombre}: movimiento en la madrugada", True)
        if nuevas & AL_SIN_MOVIMIENTO:
            limite = int(m["l2"] if i == 4 else m["l1"])
            self.registrar_evento(f"ALARMA {nombre}: sin movimiento por {limite // 60} min", True)
        if nuevas & AL_AGUA:
            self.registrar_evento(
                f"ALARMA {nombre}: agua corriendo más de {int(m['l1']) // 60} min", True
            )
        if nuevas & AL_GAS:
            self.registrar_evento(
                f"ALARMA {nombre}: gas detectado más de {int(m['l1']) // 60} min", True
            )
        if nuevas & AL_TEMPERATURA:
            self.registrar_evento(f"ALARMA {nombre}: temperatura {m['v1']:.1f} °C", True)

    def tic(self, ahora: float) -> None:
        with self.lock:
            hora_central = self.hora_valida(ahora)
            self.nodos_con_hora = self.nodos_con_hora or hora_central
            for nodo in self.nodos:
                if nodo.encendido:
                    nodo.revisar(ahora)
            # La puerta es la propia central: siempre vista y en línea (logicaPuerta()).
            puerta = self.vistas[0]
            m0 = self.nodos[0].mensaje(ahora, hora_central, self.noche)
            self.revisar_alarmas_nuevas(0, int(puerta.est.get("al", 0)), m0)
            puerta.est, puerta.visto, puerta.en_linea, puerta.ultimo = m0, True, True, ahora
            # Los demás llegan por ESP-NOW (atenderEspNow() y revisarConexiones()).
            for i in range(1, 5):
                nodo, vista = self.nodos[i], self.vistas[i]
                if nodo.encendido and ahora >= vista.primer_reporte:
                    m = nodo.mensaje(ahora, self.nodos_con_hora, self.noche)
                    if not vista.visto:
                        vista.visto = True
                        self.registrar_evento(f"{NOMBRES[i]} conectado")
                    elif not vista.en_linea:
                        self.registrar_evento(f"{NOMBRES[i]} reconectado")
                    self.revisar_alarmas_nuevas(i, int(vista.est.get("al", 0)), m)
                    vista.est, vista.en_linea, vista.ultimo = m, True, ahora
                elif vista.visto and vista.en_linea and ahora - vista.ultimo > NODO_SIN_CONEXION_S:
                    vista.en_linea = False
                    self.registrar_evento(f"{NOMBRES[i]} perdió la conexión", True)

    def json_estado(self, ahora: float) -> str:
        """jsonEstado(15) del firmware (§4.3)."""
        nodos = []
        for i, vista in enumerate(self.vistas):
            est = vista.est
            nodos.append(
                {
                    "id": i,
                    "nombre": NOMBRES[i],
                    "visto": vista.visto,
                    "enLinea": vista.en_linea,
                    **{
                        k: int(est.get(k, 0))
                        for k in ("hab", "al", "mov", "fl", "c1", "l1", "c2", "l2")
                    },
                    "v1": round(float(est.get("v1", 0.0)), 2),
                    "v2": round(float(est.get("v2", 0.0))),
                    "hace": int(ahora - vista.ultimo) if vista.visto else 0,
                }
            )
        estado = {
            "hora": self.texto_hora(ahora, "%d/%m/%Y %H:%M:%S"),
            "horaValida": self.hora_valida(ahora),
            "red": "wifi",
            "nodos": nodos,
            "eventos": list(reversed(self.eventos[-EVENTOS_PUBLICADOS:])),
        }
        return json.dumps(estado, ensure_ascii=False, separators=(",", ":"))

    def firma(self) -> tuple:
        """firmaEstado(): si cambia, se publica sin esperar los 5 s."""
        nodos = tuple((v.est.get("al", 0), v.est.get("hab", 0), v.en_linea) for v in self.vistas)
        return self.total_eventos, nodos

    # --------------------------------------------------------------- comandos
    def comando_remoto(self, texto: str) -> None:
        """procesarComandoRemoto(): "<nodo>:<accion>:<sub>" o "todo:silenciar"."""
        partes = [p for p in texto.split(":") if p]  # strtok() ignora separadores seguidos
        if len(partes) < 2:
            return
        if partes[0] == "todo" and partes[1] == "silenciar":
            self.silenciar_todo("App remota:")
        else:
            sub = atoi(partes[2]) if len(partes) > 2 else 0
            self.ejecutar(atoi(partes[0]), partes[1], sub, "App remota:")

    def ejecutar(self, nodo: int, accion: str, sub: int, origen: str) -> None:
        """ejecutarComando(): manda el comando y lo anota en la bitácora."""
        with self.lock:
            if accion not in VERBOS or not 0 <= nodo < 5:
                return
            if not self.enviar(nodo, accion, sub):
                return  # nodo nunca visto: el firmware lo descarta sin avisar
            presencia = " (presencia)" if nodo == 4 and sub == 1 else ""
            self.registrar_evento(f"{origen} {VERBOS[accion]} {NOMBRES[nodo]}{presencia}")

    def enviar(self, nodo: int, accion: str, sub: int) -> bool:
        """enviarComando(): la puerta lo aplica al instante; los demás nodos, por ESP-NOW."""
        if nodo == 0:
            self.nodos[0].comando(accion, sub, time.monotonic())
            return True
        if not self.vistas[nodo].visto:
            return False
        threading.Timer(RETARDO_ESPNOW_S, self._aplicar_en_nodo, (nodo, accion, sub)).start()
        return True

    def _aplicar_en_nodo(self, nodo: int, accion: str, sub: int) -> None:
        with self.lock:
            if self.nodos[nodo].encendido:  # si está apagado, el mensaje se pierde
                self.nodos[nodo].comando(accion, sub, time.monotonic())

    def silenciar_todo(self, origen: str) -> None:
        with self.lock:
            for i, vista in enumerate(self.vistas):
                if vista.est.get("al"):
                    self.enviar(i, "silenciar", 0)
            self.registrar_evento(f"{origen} silenció todas las alarmas")

    def cambiar_noche(self) -> None:
        """Cambio de horario de la habitación: fijarHabilitado(!noche), sin evento de la central."""
        with self.lock:
            self.noche = not self.noche
            habitacion = self.nodos[1]
            if habitacion.encendido:
                habitacion.comando("desactivar" if self.noche else "activar", 0, time.monotonic())

    # ------------------------------------------------------------------- MQTT
    def _crear_cliente(self) -> mqtt.Client:
        args = self.args
        cliente = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"central-{args.casa}",
            protocol=mqtt.MQTTv311,
        )
        cliente.username_pw_set(args.usuario or args.casa, args.clave)
        cliente.will_set(self.topico_online, "0", qos=1, retain=True)
        cliente.reconnect_delay_set(min_delay=1, max_delay=10)
        if args.tls:
            if args.ca:
                cliente.tls_set(ca_certs=args.ca)
            else:  # como WiFiClientSecure::setInsecure() del firmware: cifra pero no valida
                cliente.tls_set(cert_reqs=ssl.CERT_NONE)
                cliente.tls_insecure_set(True)
        cliente.on_connect = self._al_conectar
        cliente.on_disconnect = self._al_desconectar
        cliente.on_message = self._al_recibir
        return cliente

    def _al_conectar(self, cliente, _datos, _banderas, codigo, _propiedades) -> None:
        if codigo.is_failure:
            print(f"[MQTT] conexión rechazada: {codigo} (revisa usuario y clave)")
            return
        cliente.publish(self.topico_online, "1", qos=0, retain=True)
        cliente.subscribe(self.topico_cmd, qos=1)
        with self.lock:
            self.conectado = True
            self.firma_anterior = None  # publica el estado de inmediato
        print(f"[MQTT] conectado como central-{self.args.casa}")

    def _al_desconectar(self, _cliente, _datos, _banderas, codigo, _propiedades) -> None:
        with self.lock:
            self.conectado = False
        print(f"[MQTT] desconectado ({codigo})")

    def _al_recibir(self, _cliente, _datos, mensaje) -> None:
        texto = mensaje.payload[:47].decode("utf-8", errors="replace")  # buffer de 48 del firmware
        print(f"[cmd] {texto}")
        self.comando_remoto(texto)

    def conectar(self) -> None:
        self.cliente.connect_async(self.args.host, self.args.puerto, keepalive=30)
        self.cliente.loop_start()

    def cortar(self) -> None:
        """Cierra el socket sin DISCONNECT, como un corte de luz: el broker publica el LWT."""
        self.cliente.loop_stop()
        sock = self.cliente.socket()
        if sock is not None:
            sock.close()
        with self.lock:
            self.conectado = False

    def reiniciar(self) -> None:
        self.cortar()
        print("[central] reiniciando…")
        with self.lock:
            self.arrancar(time.monotonic())
        time.sleep(SEGUNDOS_WIFI / 2)
        self.conectar()

    def publicar_si_toca(self, ahora: float) -> None:
        with self.lock:
            if not self.conectado:
                return
            firma = self.firma()
            if (
                firma == self.firma_anterior
                and ahora - self.ultima_publicacion < INTERVALO_PUBLICACION_S
            ):
                return
            self.firma_anterior, self.ultima_publicacion = firma, ahora
            carga = self.json_estado(ahora).encode()
        self.cliente.publish(self.topico_estado, carga, qos=0, retain=True)
        if self.args.verboso:
            print(f"[estado] publicado ({len(carga)} bytes)")

    def bucle(self) -> None:
        while not self.detener.wait(0.2):
            ahora = time.monotonic()
            self.tic(ahora)
            self.publicar_si_toca(ahora)

    # ------------------------------------------------------------------- menú
    def orden(self, linea: str) -> bool:
        """Aplica una orden del menú. Devuelve False para salir."""
        partes = linea.split()
        if not partes:
            return True
        orden, resto = partes[0].lower(), partes[1:]
        ahora = time.monotonic()
        if orden in ("q", "salir"):
            return False
        if orden in ("ayuda", "h", "?"):
            print(AYUDA)
        elif orden == "b":
            self.silenciar_todo("Botón de la central:")
        elif orden == "n":
            self.cambiar_noche()
            print(
                "Habitación en horario "
                + ("nocturno (pausa automática)" if self.noche else "de día")
            )
        elif orden == "r":
            self.reiniciar()
        elif orden == "c":
            if self.conectado:
                self.cortar()
                print(
                    "Conexión cortada sin DISCONNECT: el broker publicará el LWT. 'c' para reconectar."
                )
            else:
                self.conectar()
        elif orden in ("w", "espera"):
            try:
                segundos = float(resto[0]) if resto else 1.0
            except ValueError:
                print("Uso: w <segundos>")
            else:
                self.detener.wait(segundos)
        elif orden == "e":
            with self.lock:
                print(json.dumps(json.loads(self.json_estado(ahora)), ensure_ascii=False, indent=2))
        elif orden in ("a", "s", "m", "ok", "x"):
            if not resto or not resto[0].isdigit() or int(resto[0]) > 4:
                print("Falta el número de nodo (0 a 4). Escribe 'ayuda'.")
            else:
                self._orden_de_nodo(orden, int(resto[0]), resto[1:], ahora)
        else:
            print("Orden desconocida. Escribe 'ayuda'.")
        return True

    def _orden_de_nodo(self, orden: str, n: int, resto: list[str], ahora: float) -> None:
        with self.lock:
            nodo = self.nodos[n]
            if orden == "x":
                if n == 0:
                    print("La puerta es la propia central: usa 'r' para reiniciarla.")
                elif nodo.encendido:
                    nodo.encendido = False
                    print(f"{NOMBRES[n]} apagado: la central lo dará por perdido a los 20 s.")
                else:
                    nodo.encender(ahora)
                    self.vistas[n].primer_reporte = ahora + 1.5
                    print(f"{NOMBRES[n]} encendido.")
                return
            if not nodo.encendido:
                print(f"{NOMBRES[n]} está apagado ('x {n}' para encenderlo).")
            elif orden == "a":
                tipo = resto[0] if resto else TIPOS_POR_NODO[n][0]
                error = nodo.disparar(tipo, ahora)
                print(f"No se pudo: {error}." if error else f"Alarma '{tipo}' en {NOMBRES[n]}.")
            elif orden == "s":
                nodo.comando("silenciar", 0, ahora)
            elif orden == "m":
                nodo.movimiento(ahora)
            elif orden == "ok":
                nodo.normalizar()

    def menu(self) -> None:
        """Órdenes desde el teclado o, sin terminal, desde una tubería (una por línea)."""
        interactivo = sys.stdin.isatty()
        if interactivo:
            print(AYUDA)
        while True:
            if interactivo:
                try:
                    linea = input("> ")
                except EOFError:
                    return
            else:
                linea = sys.stdin.readline()
                if not linea:
                    print("Sin más órdenes: la central sigue publicando hasta que la detengan.")
                    while not self.detener.wait(0.5):  # con pausas: Ctrl+C la detiene
                        pass
                    return
                if linea.strip():
                    print(f"> {linea.strip()}")
            if not self.orden(linea):
                return


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de la central de alarmas (§13.3).")
    parser.add_argument(
        "--casa", required=True, help="ID_CASA de la central (también es su usuario MQTT)"
    )
    parser.add_argument(
        "--clave",
        default=os.environ.get("CLAVE_CENTRAL"),
        help="clave MQTT (o la variable CLAVE_CENTRAL)",
    )
    parser.add_argument("--usuario", help="usuario MQTT; por defecto, el ID_CASA")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--puerto", type=int, default=1883)
    parser.add_argument("--tls", action="store_true", help="MQTT sobre TLS, como la central real")
    parser.add_argument(
        "--ca", help="CA para validar el broker; sin ella, TLS sin validar (setInsecure)"
    )
    parser.add_argument(
        "--sin-hora", type=float, default=5, help="segundos sin hora NTP tras cada arranque"
    )
    parser.add_argument(
        "--duracion", type=float, help="corre N segundos sin menú y sale como un corte de luz"
    )
    parser.add_argument(
        "-v", "--verboso", action="store_true", help="avisa cada publicación de estado"
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{4,40}", args.casa):
        parser.error("--casa debe tener minúsculas, números y guiones (4 a 40)")
    if not args.clave:
        parser.error("falta --clave (o la variable CLAVE_CENTRAL)")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

    central = Central(args)
    threading.Thread(target=central.bucle, daemon=True).start()
    central.conectar()
    try:
        if args.duracion:
            central.detener.wait(args.duracion)
        else:
            central.menu()
    except KeyboardInterrupt:
        pass
    finally:
        central.detener.set()
        central.cortar()
        print("Central apagada: el broker publicará el LWT.")


if __name__ == "__main__":
    main()
