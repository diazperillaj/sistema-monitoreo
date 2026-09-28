#include <Arduino.h>   // debe ir primero: define uint8_t, uint32_t, etc.
// =====================================================================
//  NODO 5 — COCINA (GAS / TEMPERATURA / PRESENCIA)
//  ESP32 + sensor MQ (MQ-2 / MQ-5 / MQ-6) + DS18B20 + PIR + módulo buzzer
//
//  - Gas por encima del umbral de forma continua durante 4 min -> alarma.
//  - Temperatura > 56 °C -> alarma inmediata.
//  - Sin movimiento durante 20 min -> alarma (el movimiento reinicia el contador).
//  - Desde la app: "Gas y temperatura" y "Presencia" se activan/desactivan
//    por separado.
//
//  Librerías: OneWire (Paul Stoffregen) y DallasTemperature (Miles Burton)
//  IMPORTANTE: la salida AO del MQ es de 0-5 V -> usa divisor de tensión
//  (ver README) y un pin ADC1 (GPIO 32-39); ADC2 no funciona con WiFi.
// =====================================================================

// ------------------------- CONFIGURACIÓN -----------------------------
#define NODO_ID              NODO_COCINA_GAS
#define SSID_CASA            "TU_RED_WIFI"
#define PIN_PIR              27
#define PIN_BUZZER           26
#define PIN_BOTON            0
#define PIN_MQ               34          // ADC1
#define PIN_DS18B20          4           // con resistencia 4.7 kΩ a 3.3 V
#define BUZZER_NIVEL_ACTIVO  HIGH

const int      UMBRAL_GAS               = 1800;      // 0-4095: CALIBRAR con tu sensor
const int      HISTERESIS_GAS           = 150;
const uint32_t LIMITE_GAS_S             = 4UL * 60;  // 4 minutos
const float    TEMPERATURA_MAXIMA       = 56.0f;     // °C
const uint32_t LIMITE_SIN_MOV_S         = 20UL * 60; // 20 minutos
const unsigned long CALENTAMIENTO_MQ    = 120000UL;  // 2 min de precalentamiento
const unsigned long CALENTAMIENTO_PIR   = 60000UL;
const unsigned long GRACIA_TEMP_MS      = 120000UL;  // tras silenciar, 2 min sin re-alarmar por temperatura
const bool     MOVIMIENTO_APAGA_ALARMA  = false;
// ---------------------------------------------------------------------

#include "nodo_espnow.h"
#include <Preferences.h>
#include <OneWire.h>
#include <DallasTemperature.h>

Preferences prefs;
OneWire oneWire(PIN_DS18B20);
DallasTemperature sensorTemp(&oneWire);

bool habGas = true;        // gas + temperatura
bool habPir = true;        // presencia
uint8_t alarmas = 0;

int  lecturaGas = 0;
bool gasPresente = false;
bool contandoGas = false;
unsigned long inicioGas = 0;

float temperatura = 0;
bool  errorTemp = false;
unsigned long ultimoSilencio = 0;
bool  silenciadoAlgunaVez = false;

bool movimiento = false;
unsigned long ultimoMovimiento = 0;

void guardar() { prefs.putBool("hab", habGas); prefs.putBool("hab2", habPir); }

void aplicarComando(uint8_t comando, uint8_t sub) {
  switch (comando) {
    case CMD_ACTIVAR:
      if (sub == 1) { habPir = true; ultimoMovimiento = millis(); }
      else          { habGas = true; contandoGas = false; }
      guardar();
      break;
    case CMD_DESACTIVAR:
      if (sub == 1) { habPir = false; alarmas &= ~AL_SIN_MOVIMIENTO; }
      else          { habGas = false; contandoGas = false; alarmas &= ~(AL_GAS | AL_TEMPERATURA); }
      guardar();
      break;
    case CMD_SILENCIAR:
      alarmas = 0;
      inicioGas = millis();            // si sigue habiendo gas, vuelve a contar 4 min
      ultimoMovimiento = millis();
      ultimoSilencio = millis();
      silenciadoAlgunaVez = true;
      break;
  }
}

void llenarEstado(Mensaje &m) {
  m.habilitado = (habGas ? HAB_PRINCIPAL : 0) | (habPir ? HAB_SECUNDARIO : 0);
  m.alarmas    = alarmas;
  m.movimiento = movimiento;
  m.limite     = LIMITE_GAS_S;
  m.limite2    = LIMITE_SIN_MOV_S;
  m.valor1     = temperatura;
  m.valor2     = lecturaGas;
  if (habGas && contandoGas) { m.flags |= FL_CONTANDO1; m.contador = (millis() - inicioGas) / 1000; }
  if (habPir) { m.flags |= FL_CONTANDO2; m.contador2 = (millis() - ultimoMovimiento) / 1000; }
  if (millis() < CALENTAMIENTO_MQ) m.flags |= FL_CALENTANDO;
  if (errorTemp) m.flags |= FL_ERROR_SENSOR;
}

int leerGas() {
  long suma = 0;
  for (int i = 0; i < 10; i++) { suma += analogRead(PIN_MQ); delayMicroseconds(200); }
  return suma / 10;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  analogSetPinAttenuation(PIN_MQ, ADC_11db);   // rango completo 0-3.3 V
  buzzerIniciar();

  prefs.begin("nodo", false);
  habGas = prefs.getBool("hab", true);
  habPir = prefs.getBool("hab2", true);

  sensorTemp.begin();
  sensorTemp.requestTemperatures();             // primera lectura bloqueante (evita el 85 °C de arranque)
  temperatura = sensorTemp.getTempCByIndex(0);
  errorTemp = (temperatura == DEVICE_DISCONNECTED_C);
  sensorTemp.setWaitForConversion(false);
  sensorTemp.requestTemperatures();

  iniciarComunicacion();
  ultimoMovimiento = millis();
}

void loop() {
  atenderComunicacion();
  bool cambio = false;
  unsigned long ahora = millis();

  // ---------- GAS (cada 500 ms) ----------
  static unsigned long tGas = 0;
  if (ahora - tGas >= 500) {
    tGas = ahora;
    lecturaGas = leerGas();
    bool antes = gasPresente;
    if (ahora < CALENTAMIENTO_MQ)                         gasPresente = false;
    else if (!gasPresente && lecturaGas > UMBRAL_GAS)      gasPresente = true;
    else if (gasPresente && lecturaGas < UMBRAL_GAS - HISTERESIS_GAS) gasPresente = false;
    if (antes != gasPresente) { cambio = true; Serial.printf("Gas %s (%d)\n", gasPresente ? "DETECTADO" : "normal", lecturaGas); }
  }
  if (habGas && gasPresente) {
    if (!contandoGas) { contandoGas = true; inicioGas = ahora; }
    if (!(alarmas & AL_GAS) && ahora - inicioGas >= LIMITE_GAS_S * 1000UL) {
      alarmas |= AL_GAS; cambio = true;
      Serial.println("¡ALARMA! Fuga de gas por más de 4 minutos");
    }
  } else {
    contandoGas = false;
  }

  // ---------- TEMPERATURA (cada 1 s, sin bloquear) ----------
  static unsigned long tTemp = 0;
  if (ahora - tTemp >= 1000) {
    tTemp = ahora;
    float t = sensorTemp.getTempCByIndex(0);
    sensorTemp.requestTemperatures();
    errorTemp = (t == DEVICE_DISCONNECTED_C);
    if (!errorTemp) temperatura = t;
    bool enGracia = silenciadoAlgunaVez && (ahora - ultimoSilencio < GRACIA_TEMP_MS);
    if (habGas && !errorTemp && temperatura > TEMPERATURA_MAXIMA &&
        !(alarmas & AL_TEMPERATURA) && !enGracia) {
      alarmas |= AL_TEMPERATURA; cambio = true;
      Serial.printf("¡ALARMA! Temperatura %.1f °C\n", temperatura);
    }
  }

  // ---------- PRESENCIA (PIR) ----------
  bool pir = (ahora > CALENTAMIENTO_PIR) && digitalRead(PIN_PIR) == HIGH;
  if (pir != movimiento) { movimiento = pir; cambio = true; }
  if (movimiento) {
    ultimoMovimiento = ahora;
    if (MOVIMIENTO_APAGA_ALARMA && (alarmas & AL_SIN_MOVIMIENTO)) { alarmas &= ~AL_SIN_MOVIMIENTO; cambio = true; }
  }
  if (habPir && !(alarmas & AL_SIN_MOVIMIENTO) &&
      ahora - ultimoMovimiento >= LIMITE_SIN_MOV_S * 1000UL) {
    alarmas |= AL_SIN_MOVIMIENTO; cambio = true;
    Serial.println("¡ALARMA! 20 minutos sin movimiento en la cocina");
  }

  if (botonPresionado()) { aplicarComando(CMD_SILENCIAR, 0); cambio = true; }

  // Gas/temperatura: pitido más rápido para diferenciarlo
  buzzerActualizar(alarmas != 0, (alarmas & (AL_GAS | AL_TEMPERATURA)) ? 150 : 400);
  if (cambio) enviarEstado();
  delay(20);
}
