#include <Arduino.h>   // debe ir primero: define uint8_t, uint32_t, etc.
// =====================================================================
//  NODO 4 — COCINA (AGUA)
//  ESP32 + sensor de flujo (YF-S201 o similar) + módulo buzzer
//
//  - Si el agua corre de forma continua más de 8 minutos -> alarma.
//  - Pausas cortas (< 3 s) no reinician el conteo; si la llave se cierra
//    el contador vuelve a cero.
//  - Se puede activar / desactivar desde la app.
// =====================================================================

// ------------------------- CONFIGURACIÓN -----------------------------
#define NODO_ID              NODO_COCINA_AGUA
#define SSID_CASA            "TU_RED_WIFI"
#define PIN_FLUJO            25          // salida de pulsos del sensor (con divisor si va a 5 V)
#define PIN_BUZZER           26
#define PIN_BOTON            0
#define BUZZER_NIVEL_ACTIVO  HIGH

const uint32_t LIMITE_FLUJO_S            = 8UL * 60;  // 8 minutos
const float    PULSOS_POR_LMIN           = 7.5f;      // YF-S201: f(Hz) = 7.5 * Q(L/min)
const uint32_t PULSOS_MINIMOS            = 3;         // pulsos/segundo para considerar "hay flujo"
const unsigned long TOLERANCIA_PAUSA_MS  = 3000UL;
const bool     FLUJO_CERRADO_APAGA_ALARMA = true;     // al cerrar la llave se apaga la alarma
// ---------------------------------------------------------------------

#include "nodo_espnow.h"
#include <Preferences.h>

Preferences prefs;
bool habilitado = true;
uint8_t alarmas = 0;

volatile uint32_t pulsos = 0;
portMUX_TYPE muxFlujo = portMUX_INITIALIZER_UNLOCKED;
void IRAM_ATTR isrFlujo() {
  portENTER_CRITICAL_ISR(&muxFlujo);
  pulsos++;
  portEXIT_CRITICAL_ISR(&muxFlujo);
}

float caudal = 0;                      // L/min
bool hayFlujo = false;
bool contando = false;
unsigned long inicioFlujo = 0, ultimoFlujo = 0, ultimaMedida = 0;

void fijarHabilitado(bool v) {
  if (habilitado != v) prefs.putBool("hab", v);
  habilitado = v;
  inicioFlujo = millis();
  if (!v) alarmas = 0;
}

void aplicarComando(uint8_t comando, uint8_t sub) {
  switch (comando) {
    case CMD_ACTIVAR:    fijarHabilitado(true);  break;
    case CMD_DESACTIVAR: fijarHabilitado(false); break;
    case CMD_SILENCIAR:  alarmas = 0; inicioFlujo = millis(); break;
  }
}

void llenarEstado(Mensaje &m) {
  m.habilitado = habilitado ? HAB_PRINCIPAL : 0;
  m.alarmas    = alarmas;
  m.movimiento = hayFlujo;
  m.limite     = LIMITE_FLUJO_S;
  m.valor1     = caudal;
  if (contando && habilitado) {
    m.flags   |= FL_CONTANDO1;
    m.contador = (millis() - inicioFlujo) / 1000;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_FLUJO, INPUT_PULLUP);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLUJO), isrFlujo, FALLING);
  buzzerIniciar();
  prefs.begin("nodo", false);
  habilitado = prefs.getBool("hab", true);
  iniciarComunicacion();
}

void loop() {
  atenderComunicacion();
  bool cambio = false;
  unsigned long ahora = millis();

  // Medición cada segundo
  if (ahora - ultimaMedida >= 1000) {
    float dt = (ahora - ultimaMedida) / 1000.0f;
    ultimaMedida = ahora;
    portENTER_CRITICAL(&muxFlujo);
    uint32_t p = pulsos;
    pulsos = 0;
    portEXIT_CRITICAL(&muxFlujo);

    caudal = (p / dt) / PULSOS_POR_LMIN;
    if (p >= PULSOS_MINIMOS) {
      ultimoFlujo = ahora;
      if (!contando) { contando = true; inicioFlujo = ahora; cambio = true; Serial.println("Agua corriendo"); }
    }
  }

  bool flujoAntes = hayFlujo;
  hayFlujo = contando;
  if (contando && ahora - ultimoFlujo > TOLERANCIA_PAUSA_MS) {
    contando = false;                        // llave cerrada: contador a cero
    hayFlujo = false;
    caudal = 0;
    Serial.println("Llave cerrada");
    if (FLUJO_CERRADO_APAGA_ALARMA) alarmas &= ~AL_AGUA;
  }
  if (flujoAntes != hayFlujo) cambio = true;

  if (habilitado && contando && !(alarmas & AL_AGUA) &&
      ahora - inicioFlujo >= LIMITE_FLUJO_S * 1000UL) {
    alarmas |= AL_AGUA;
    cambio = true;
    Serial.println("¡ALARMA! Agua corriendo más de 8 minutos");
  }

  if (botonPresionado()) { aplicarComando(CMD_SILENCIAR, 0); cambio = true; }

  buzzerActualizar(alarmas != 0);
  if (cambio) enviarEstado();
  delay(20);
}
