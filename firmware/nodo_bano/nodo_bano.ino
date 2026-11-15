#include <Arduino.h>   // debe ir primero: define uint8_t, uint32_t, etc.
// =====================================================================
//  NODO 3 — BAÑO
//  ESP32 + sensor PIR (HC-SR501) + módulo buzzer
//
//  - El contador arranca cuando se detecta movimiento (alguien entra).
//  - Cada movimiento reinicia el contador.
//  - Si pasan 10 minutos sin movimiento -> alarma.
//  - Tras silenciar la alarma vuelve a "esperando movimiento".
//  - Se puede activar / desactivar desde la app.
// =====================================================================

// ------------------------- CONFIGURACIÓN -----------------------------
#define NODO_ID              NODO_BANO
#define SSID_CASA            "TU_RED_WIFI"
#define PIN_PIR              27
#define PIN_BUZZER           26
#define PIN_BOTON            0
#define BUZZER_NIVEL_ACTIVO  HIGH

const uint32_t LIMITE_SIN_MOV_S        = 10UL * 60;  // 10 minutos
const unsigned long CALENTAMIENTO_PIR  = 60000UL;
const bool     MOVIMIENTO_APAGA_ALARMA = false;
// ---------------------------------------------------------------------

#include "nodo_espnow.h"
#include <Preferences.h>

Preferences prefs;
bool habilitado = true;
uint8_t alarmas = 0;
bool movimiento = false;
bool contando = false;                 // false = esperando que alguien entre
unsigned long ultimoMovimiento = 0;

// Diagnóstico: eventos sueltos + una línea de estado cada 5 s (monitor serie a 115200)
void logDiagnostico() {
  static bool calentandoAntes = true;
  bool calentando = millis() < CALENTAMIENTO_PIR;
  if (calentandoAntes && !calentando) { calentandoAntes = false; Serial.println("[BAÑO] PIR listo (terminó el calentamiento)"); }
  if (!tocaLog()) return;

  char d[96];
  int n = 0;
  if (calentando) n += snprintf(d + n, sizeof(d) - n, "PIR: calentando (faltan %lus)", (CALENTAMIENTO_PIR - millis()) / 1000);
  else            n += snprintf(d + n, sizeof(d) - n, "PIR: %s", movimiento ? "MOVIMIENTO" : "quieto");
  n += snprintf(d + n, sizeof(d) - n, " | %s", habilitado ? "activado" : "DESACTIVADO");
  if (contando) snprintf(d + n, sizeof(d) - n, " | contador %lu/%lus", (millis() - ultimoMovimiento) / 1000, (unsigned long)LIMITE_SIN_MOV_S);
  else          snprintf(d + n, sizeof(d) - n, " | contador detenido");
  logEstado("BAÑO", alarmas, d);
}

void fijarHabilitado(bool v) {
  if (habilitado != v) prefs.putBool("hab", v);
  habilitado = v;
  contando = false;
  if (!v) alarmas = 0;
}

void aplicarComando(uint8_t comando, uint8_t sub) {
  switch (comando) {
    case CMD_ACTIVAR:    fijarHabilitado(true);  Serial.println("[BAÑO] Vigilancia ACTIVADA");    break;
    case CMD_DESACTIVAR: fijarHabilitado(false); Serial.println("[BAÑO] Vigilancia DESACTIVADA"); break;
    case CMD_SILENCIAR:  alarmas = 0; contando = false; Serial.println("[BAÑO] Alarma silenciada"); break;
  }
}

void llenarEstado(Mensaje &m) {
  m.habilitado = habilitado ? HAB_PRINCIPAL : 0;
  m.alarmas    = alarmas;
  m.movimiento = movimiento;
  m.limite     = LIMITE_SIN_MOV_S;
  if (contando) {
    m.flags   |= FL_CONTANDO1;
    m.contador = (millis() - ultimoMovimiento) / 1000;
  }
  if (millis() < CALENTAMIENTO_PIR) m.flags |= FL_CALENTANDO;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  buzzerIniciar();
  prefs.begin("nodo", false);
  habilitado = prefs.getBool("hab", true);
  Serial.println();
  Serial.println("========== NODO BAÑO ==========");
  Serial.printf("[BAÑO] Vigilancia %s (guardado en memoria)\n", habilitado ? "activada" : "DESACTIVADA");
  iniciarComunicacion();
}

void loop() {
  atenderComunicacion();
  bool cambio = false;

  bool pir = (millis() > CALENTAMIENTO_PIR) && digitalRead(PIN_PIR) == HIGH;
  if (pir != movimiento) {
    movimiento = pir; cambio = true;
    Serial.println(movimiento ? "[BAÑO] PIR: movimiento detectado" : "[BAÑO] PIR: sin movimiento");
  }

  if (movimiento) {
    ultimoMovimiento = millis();                      // reinicia el contador
    if (habilitado && !contando) { contando = true; cambio = true; Serial.println("Baño: contador iniciado"); }
    if (MOVIMIENTO_APAGA_ALARMA && (alarmas & AL_SIN_MOVIMIENTO)) { alarmas = 0; cambio = true; }
  }

  if (habilitado && contando && !(alarmas & AL_SIN_MOVIMIENTO) &&
      millis() - ultimoMovimiento >= LIMITE_SIN_MOV_S * 1000UL) {
    alarmas |= AL_SIN_MOVIMIENTO;
    contando = false;
    cambio = true;
    Serial.println("¡ALARMA! 10 minutos sin movimiento en el baño");
  }

  if (botonPresionado()) { Serial.println("[BAÑO] Botón BOOT presionado"); aplicarComando(CMD_SILENCIAR, 0); cambio = true; }

  buzzerActualizar(alarmas != 0);
  if (cambio) enviarEstado();
  logDiagnostico();
  delay(20);
}
