#include <Arduino.h>   // debe ir primero: define uint8_t, uint32_t, etc.
// =====================================================================
//  NODO 2 — HABITACIÓN
//  ESP32 + sensor PIR (HC-SR501) + módulo buzzer
//
//  - Alarma si NO hay movimiento durante 30 minutos. Cualquier movimiento
//    reinicia el contador.
//  - Se desactiva automáticamente de 22:00 a 06:00 y se reactiva a las 06:00.
//  - El cuidador puede activarla / desactivarla desde la app en cualquier
//    momento (el cambio se mantiene hasta el siguiente cambio de horario).
//  - La hora la recibe de la central por ESP-NOW.
// =====================================================================

// ------------------------- CONFIGURACIÓN -----------------------------
#define NODO_ID              NODO_HABITACION
#define SSID_CASA            "TU_RED_WIFI"   // sólo el NOMBRE, para hallar el canal
#define PIN_PIR              26
#define PIN_BUZZER           27
#define PIN_BOTON            0               // botón BOOT: silenciar en sitio
#define BUZZER_NIVEL_ACTIVO  HIGH            // pon LOW si tu módulo suena con nivel bajo

const uint32_t LIMITE_SIN_MOV_S       = 30UL * 60;  // 30 minutos
const int      HORA_INICIO_NOCHE      = 22;         // 22:00
const int      HORA_FIN_NOCHE         = 6;          // 06:00
const unsigned long CALENTAMIENTO_PIR = 30000UL;    // el PIR necesita ~1 min al encender
const bool     MOVIMIENTO_APAGA_ALARMA = false;     // true: si la persona se mueve, la alarma se apaga sola
// ---------------------------------------------------------------------

#include "nodo_espnow.h"
#include <Preferences.h>

Preferences prefs;
bool habilitado = true;
uint8_t alarmas = 0;
bool movimiento = false;
unsigned long ultimoMovimiento = 0;
int estadoNocheAnterior = -1;          // -1 = aún sin hora

// Diagnóstico: eventos sueltos + una línea de estado cada 5 s (monitor serie a 115200)
void logDiagnostico() {
  static bool calentandoAntes = true;
  bool calentando = millis() < CALENTAMIENTO_PIR;
  if (calentandoAntes && !calentando) { calentandoAntes = false; Serial.println("[HABITACIÓN] PIR listo (terminó el calentamiento)"); }
  if (!tocaLog()) return;

  char d[128];
  int n = 0;
  if (calentando) n += snprintf(d + n, sizeof(d) - n, "PIR: calentando (faltan %lus)", (CALENTAMIENTO_PIR - millis()) / 1000);
  else            n += snprintf(d + n, sizeof(d) - n, "PIR: %s", movimiento ? "MOVIMIENTO" : "quieto");
  n += snprintf(d + n, sizeof(d) - n, " | %s", habilitado ? "activada" : "DESACTIVADA");
  if (horaValida()) n += snprintf(d + n, sizeof(d) - n, " | %s", enRangoHoras(HORA_INICIO_NOCHE, HORA_FIN_NOCHE) ? "horario nocturno" : "horario de día");
  if (habilitado) snprintf(d + n, sizeof(d) - n, " | contador %lu/%lus", (millis() - ultimoMovimiento) / 1000, (unsigned long)LIMITE_SIN_MOV_S);
  logEstado("HABITACIÓN", alarmas, d);
}

void fijarHabilitado(bool v) {
  if (habilitado != v) prefs.putBool("hab", v);
  habilitado = v;
  ultimoMovimiento = millis();         // el contador arranca de cero
  if (!v) alarmas = 0;
  Serial.printf("Habitación %s\n", v ? "ACTIVADA" : "DESACTIVADA");
}

void aplicarComando(uint8_t comando, uint8_t sub) {
  switch (comando) {
    case CMD_ACTIVAR:    fijarHabilitado(true);  break;
    case CMD_DESACTIVAR: fijarHabilitado(false); break;
    case CMD_SILENCIAR:  alarmas = 0; ultimoMovimiento = millis(); Serial.println("[HABITACIÓN] Alarma silenciada"); break;
  }
}

void llenarEstado(Mensaje &m) {
  m.habilitado = habilitado ? HAB_PRINCIPAL : 0;
  m.alarmas    = alarmas;
  m.movimiento = movimiento;
  m.limite     = LIMITE_SIN_MOV_S;
  if (habilitado) {
    m.flags   |= FL_CONTANDO1;
    m.contador = (millis() - ultimoMovimiento) / 1000;
  }
  if (millis() < CALENTAMIENTO_PIR) m.flags |= FL_CALENTANDO;
  if (horaValida() && enRangoHoras(HORA_INICIO_NOCHE, HORA_FIN_NOCHE)) m.flags |= FL_HORARIO_NOCTURNO;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  buzzerIniciar();
  prefs.begin("nodo", false);
  habilitado = prefs.getBool("hab", true);
  Serial.println();
  Serial.println("========== NODO HABITACIÓN ==========");
  Serial.printf("[HABITACIÓN] Vigilancia %s (guardado en memoria)\n", habilitado ? "activada" : "DESACTIVADA");
  iniciarComunicacion();
  ultimoMovimiento = millis();
}

void loop() {
  atenderComunicacion();
  bool cambio = false;

  // 1) Sensor PIR
  bool pir = (millis() > CALENTAMIENTO_PIR) && digitalRead(PIN_PIR) == HIGH;
  if (pir != movimiento) {
    movimiento = pir; cambio = true;
    Serial.println(movimiento ? "[HABITACIÓN] PIR: movimiento detectado" : "[HABITACIÓN] PIR: sin movimiento");
  }
  if (movimiento) {
    ultimoMovimiento = millis();                      // reinicia el contador
    if (MOVIMIENTO_APAGA_ALARMA && (alarmas & AL_SIN_MOVIMIENTO)) { alarmas = 0; cambio = true; }
  }

  // 2) Horario nocturno automático (sólo en los cambios 22:00 y 06:00)
  if (horaValida()) {
    int noche = enRangoHoras(HORA_INICIO_NOCHE, HORA_FIN_NOCHE) ? 1 : 0;
    if (noche != estadoNocheAnterior) {
      estadoNocheAnterior = noche;
      Serial.printf("[HABITACIÓN] Cambio de horario: %s\n", noche ? "empieza la noche" : "empieza el día");
      fijarHabilitado(!noche);
      cambio = true;
    }
  }

  // 3) ¿30 minutos sin movimiento?
  if (habilitado && !(alarmas & AL_SIN_MOVIMIENTO) &&
      millis() - ultimoMovimiento >= LIMITE_SIN_MOV_S * 1000UL) {
    alarmas |= AL_SIN_MOVIMIENTO;
    cambio = true;
    Serial.println("¡ALARMA! Sin movimiento en la habitación");
  }

  // 4) Botón local
  if (botonPresionado()) { Serial.println("[HABITACIÓN] Botón BOOT presionado"); aplicarComando(CMD_SILENCIAR, 0); cambio = true; }

  buzzerActualizar(alarmas != 0);
  if (cambio) enviarEstado();
  logDiagnostico();
  delay(20);
}
