// =====================================================================
//  bateria.h  —  Batería de litio de 3.7 V (1000 mAh) de cada ESP32
//  (este archivo debe ser idéntico en las 5 carpetas)
//
//  Conexión:  BAT+ ── 220 kΩ ──┬── 220 kΩ ── GND
//                              ├── D34 (ADC1, solo entrada)
//                              └── 100 nF ── GND
//  El pin ve la mitad del voltaje (4.20 V → 2.10 V). Con resistencias tan
//  altas el condensador es necesario: sin él la lectura salta.
//
//  - Porcentaje: con la curva típica de una celda de litio (no es lineal).
//  - Cargando: ningún cable lo dice; se deduce del voltaje. Al conectar el
//    cargador el voltaje sube de golpe y sigue subiendo; al quitarlo, baja
//    de golpe. Se compara la lectura con la de hace 30 s y, para lo lento,
//    con la de hace 5 min. Puede equivocarse unos minutos.
//  - BAT_BAJA y BAT_LLENA quedan puestas con histéresis: la app avisa una
//    sola vez cada vez que se cruza el umbral, no a cada décima.
//
//  Uso: bateriaIniciar() en setup(), bateriaActualizar() en cada vuelta de
//  loop() (lee cada segundo) y bateriaLlenar(m) al armar el Mensaje.
// =====================================================================
#pragma once
#include <Arduino.h>
#include "protocolo.h"

#ifndef PIN_BATERIA
#define PIN_BATERIA 34                         // ADC1: el ADC2 no funciona con el WiFi encendido
#endif

const float   BAT_DIVISOR          = 2.0f;    // 220 kΩ / 220 kΩ
const float   BAT_V_MIN_PRESENTE   = 2.80f;   // menos que esto: no hay batería (pin a 0 V)
const float   BAT_V_LLENA          = 4.15f;   // cargando y por encima: llena
const float   BAT_V_SUELTA_LLENA   = 4.00f;   // sin cargar y por debajo: deja de estar "llena"
const uint8_t BAT_PCT_BAJA         = 10;      // aviso para ponerla a cargar
const uint8_t BAT_PCT_SUELTA_BAJA  = 20;      // por encima deja de estar "baja"
const float   BAT_COMPENSA_CARGA   = 0.10f;   // cargando, el voltaje se lee ~0.1 V más alto
const float   BAT_CAMBIO_V         = 0.02f;   // subida o bajada que cuenta como enchufar/desenchufar
const unsigned long BAT_LECTURA_MS = 1000UL;
const unsigned long BAT_VENTANA_CORTA_MS = 30000UL;
const unsigned long BAT_VENTANA_LARGA_MS = 300000UL;

// Curva de descarga en reposo de una celda de litio de 3.7 V (voltaje -> %)
static const float   BAT_CURVA_V[] = {3.30f, 3.50f, 3.60f, 3.68f, 3.74f, 3.78f, 3.82f, 3.87f, 3.93f, 4.00f, 4.08f, 4.15f};
static const uint8_t BAT_CURVA_P[] = {0,     5,     10,    20,    30,    40,    50,    60,    70,    80,    90,    100};

static float   batVoltios   = 0;      // suavizado
static uint8_t batPct       = 0;
static bool    batPresente  = false;
static bool    batCargando  = false;
static bool    batBaja      = false;
static bool    batLlena     = false;

static uint8_t bateriaPorcentaje(float v) {
  const int n = sizeof(BAT_CURVA_V) / sizeof(BAT_CURVA_V[0]);
  if (v <= BAT_CURVA_V[0]) return 0;
  if (v >= BAT_CURVA_V[n - 1]) return 100;
  for (int i = 1; i < n; i++) {
    if (v < BAT_CURVA_V[i]) {
      float t = (v - BAT_CURVA_V[i - 1]) / (BAT_CURVA_V[i] - BAT_CURVA_V[i - 1]);
      return (uint8_t)(BAT_CURVA_P[i - 1] + t * (BAT_CURVA_P[i] - BAT_CURVA_P[i - 1]) + 0.5f);
    }
  }
  return 100;
}

static float bateriaLeerVoltios() {
  uint32_t suma = 0;
  for (int i = 0; i < 16; i++) suma += analogReadMilliVolts(PIN_BATERIA);   // calibrado de fábrica
  return (suma / 16.0f) / 1000.0f * BAT_DIVISOR;
}

static void bateriaIniciar() {
  analogSetPinAttenuation(PIN_BATERIA, ADC_11db);   // hasta ~3.1 V en el pin
}

// Lee como máximo una vez por segundo. Devuelve true si cambió algo que se muestra
// (porcentaje o banderas), para mandar el estado enseguida.
static bool bateriaActualizar() {
  static unsigned long ultimaLectura = 0, inicioCorta = 0, inicioLarga = 0;
  static float vCorta = 0, vLarga = 0;
  static bool leida = false, primera = true;
  if (leida && millis() - ultimaLectura < BAT_LECTURA_MS) return false;
  leida = true;
  ultimaLectura = millis();

  uint8_t pctAntes = batPct;
  uint8_t flagsAntes = (batPresente ? BAT_PRESENTE : 0) | (batCargando ? BAT_CARGANDO : 0) |
                       (batBaja ? BAT_BAJA : 0) | (batLlena ? BAT_LLENA : 0);

  float v = bateriaLeerVoltios();
  if (v < BAT_V_MIN_PRESENTE) {                 // sin batería: todo en cero hasta que aparezca
    batPresente = batCargando = batBaja = batLlena = false;
    batVoltios = 0; batPct = 0; primera = true;
    if (flagsAntes) Serial.println("[BATERÍA] No hay batería conectada");
    return flagsAntes != 0;
  }
  if (primera) {                                // arranque o batería recién conectada
    primera = false;
    batVoltios = vCorta = vLarga = v;
    inicioCorta = inicioLarga = millis();
    batPresente = true;
  } else {
    batVoltios += 0.2f * (v - batVoltios);      // suavizado: ~5 s de memoria
  }

  // ¿Cargando? Un salto en 30 s (enchufar o desenchufar) o una tendencia en 5 min
  if (millis() - inicioCorta >= BAT_VENTANA_CORTA_MS) {
    float d = batVoltios - vCorta;
    if (d >= BAT_CAMBIO_V && !batCargando)  { batCargando = true;  Serial.println("[BATERÍA] Conectada al cargador"); }
    if (d <= -BAT_CAMBIO_V && batCargando)  { batCargando = false; Serial.println("[BATERÍA] Desconectada del cargador"); }
    vCorta = batVoltios; inicioCorta = millis();
  }
  if (millis() - inicioLarga >= BAT_VENTANA_LARGA_MS) {
    float d = batVoltios - vLarga;
    if (d >= BAT_CAMBIO_V && !batCargando)  { batCargando = true;  Serial.println("[BATERÍA] Cargando (sube despacio)"); }
    if (d <= -BAT_CAMBIO_V && batCargando)  { batCargando = false; Serial.println("[BATERÍA] Ya no carga (baja despacio)"); }
    vLarga = batVoltios; inicioLarga = millis();
  }

  // Porcentaje: cargando, el voltaje se lee más alto de lo que en verdad tiene
  if (batCargando && batVoltios >= BAT_V_LLENA) batPct = 100;
  else batPct = bateriaPorcentaje(batCargando ? batVoltios - BAT_COMPENSA_CARGA : batVoltios);

  // Avisos con histéresis
  if (!batBaja && !batCargando && batPct <= BAT_PCT_BAJA) { batBaja = true; Serial.println("[BATERÍA] BAJA: ponla a cargar"); }
  if (batBaja && (batCargando || batPct >= BAT_PCT_SUELTA_BAJA)) batBaja = false;
  if (!batLlena && batCargando && batVoltios >= BAT_V_LLENA) { batLlena = true; Serial.println("[BATERÍA] LLENA: desconecta el cargador"); }
  if (batLlena && !batCargando && batVoltios < BAT_V_SUELTA_LLENA) batLlena = false;

  uint8_t flags = BAT_PRESENTE | (batCargando ? BAT_CARGANDO : 0) | (batBaja ? BAT_BAJA : 0) | (batLlena ? BAT_LLENA : 0);
  return flags != flagsAntes || batPct != pctAntes;
}

static void bateriaLlenar(Mensaje &m) {
  if (!batPresente) { m.bateria = BAT_SIN_DATO; m.bat_flags = 0; m.bat_v = 0; return; }
  m.bateria   = batPct;
  m.bat_flags = BAT_PRESENTE | (batCargando ? BAT_CARGANDO : 0) | (batBaja ? BAT_BAJA : 0) | (batLlena ? BAT_LLENA : 0);
  float centesimas = (batVoltios - 2.50f) * 100.0f + 0.5f;
  m.bat_v = (uint8_t)constrain(centesimas, 1.0f, 255.0f);
}

// Para el monitor serie: "87 % (3.95 V)", "64 % (4.12 V) cargando" o "sin batería"
static void bateriaTexto(char *buf, size_t n) {
  if (!batPresente) { snprintf(buf, n, "sin batería"); return; }
  snprintf(buf, n, "%u %% (%.2f V)%s%s%s", batPct, batVoltios, batCargando ? " cargando" : "",
           batBaja ? " BAJA" : "", batLlena ? " LLENA" : "");
}
