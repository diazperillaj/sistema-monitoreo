// =====================================================================
//  nodo_espnow.h — Comunicación ESP-NOW y utilidades para los NODOS
//  (habitación, baño, cocina-agua, cocina-gas). Idéntico en las 4 carpetas.
//
//  Antes de incluir este archivo, el sketch debe definir:
//    NODO_ID, SSID_CASA, PIN_BUZZER, PIN_BOTON, BUZZER_NIVEL_ACTIVO
//  y debe implementar:
//    void aplicarComando(uint8_t comando, uint8_t sub);
//    void llenarEstado(Mensaje &m);
// =====================================================================
#pragma once
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <sys/time.h>
#include <time.h>
#include "protocolo.h"

#ifndef SSID_AP_CENTRAL
#define SSID_AP_CENTRAL "AlarmaCasa"   // red propia de la central si no hay router
#endif
#ifndef CANAL_POR_DEFECTO
#define CANAL_POR_DEFECTO 1
#endif
#define INTERVALO_REPORTE_MS   3000UL   // envío periódico del estado
#define TIEMPO_SIN_CENTRAL_MS 90000UL   // si no se oye a la central, se busca de nuevo el canal

void aplicarComando(uint8_t comando, uint8_t sub);
void llenarEstado(Mensaje &m);

static const uint8_t MAC_BROADCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static uint8_t macCentral[6]          = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static bool centralConocida           = false;
static unsigned long ultimoContactoCentral = 0;
static uint8_t canalActual            = CANAL_POR_DEFECTO;

struct PaqueteRx { uint8_t mac[6]; Mensaje m; };
static QueueHandle_t colaRx = nullptr;

// ---------- Recepción (se ejecuta en la tarea WiFi: sólo encolar) ----------
static void encolarRx(const uint8_t *mac, const uint8_t *data, int len) {
  if (colaRx == nullptr || len != (int)sizeof(Mensaje)) return;
  PaqueteRx p;
  memcpy(p.mac, mac, 6);
  memcpy(&p.m, data, sizeof(Mensaje));
  if (p.m.magic != ESPNOW_MAGIC) return;
  if (p.m.tipo != MSG_TIEMPO && p.m.tipo != MSG_COMANDO) return; // sólo lo que envía la central
  xQueueSend(colaRx, &p, 0);
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
static void alRecibirEspNow(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  encolarRx(info->src_addr, data, len);
}
#else
static void alRecibirEspNow(const uint8_t *mac, const uint8_t *data, int len) {
  encolarRx(mac, data, len);
}
#endif

static void agregarPeer(const uint8_t *mac) {
  if (esp_now_is_peer_exist(mac)) return;
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, mac, 6);
  peer.channel = 0;            // 0 = canal actual
  peer.ifidx   = WIFI_IF_STA;
  peer.encrypt = false;
  esp_now_add_peer(&peer);
}

static void fijarCanal(uint8_t canal) {
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(canal, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);
}

// Busca el canal de la red WiFi de la casa (la central trabaja en ese canal)
static uint8_t buscarCanal() {
  uint8_t canal = 0;
  int n = WiFi.scanNetworks(false, true, false, 150);
  for (int i = 0; i < n; i++) {
    String s = WiFi.SSID(i);
    if (s == SSID_CASA || s == SSID_AP_CENTRAL) { canal = WiFi.channel(i); break; }
  }
  WiFi.scanDelete();
  if (canal == 0) {
    Serial.printf("[ESP-NOW] Red '%s' no encontrada, uso canal %d\n", SSID_CASA, CANAL_POR_DEFECTO);
    canal = CANAL_POR_DEFECTO;
  } else {
    Serial.printf("[ESP-NOW] Canal de la central: %u\n", canal);
  }
  return canal;
}

static bool horaValida() { return time(nullptr) > (time_t)EPOCH_MINIMO; }

// true si la hora local actual está en [horaInicio, horaFin) — admite cruzar medianoche
static bool enRangoHoras(int horaInicio, int horaFin) {
  time_t ahora = time(nullptr);
  struct tm t;
  localtime_r(&ahora, &t);
  if (horaInicio == horaFin) return false;
  if (horaInicio < horaFin) return t.tm_hour >= horaInicio && t.tm_hour < horaFin;
  return t.tm_hour >= horaInicio || t.tm_hour < horaFin;
}

static void iniciarComunicacion() {
  setenv("TZ", ZONA_HORARIA, 1);
  tzset();
  colaRx = xQueueCreate(10, sizeof(PaqueteRx));

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  WiFi.setSleep(false);            // sin ahorro de energía: recepción ESP-NOW fiable
  canalActual = buscarCanal();
  fijarCanal(canalActual);

  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESP-NOW] Error al iniciar, reiniciando...");
    delay(2000);
    ESP.restart();
  }
  esp_now_register_recv_cb(alRecibirEspNow);
  agregarPeer(MAC_BROADCAST);
  Serial.printf("[ESP-NOW] Nodo %u listo. MAC: %s\n", NODO_ID, WiFi.macAddress().c_str());
}

static void enviarEstado() {
  Mensaje m;
  memset(&m, 0, sizeof(m));
  m.magic = ESPNOW_MAGIC;
  m.tipo  = MSG_ESTADO;
  m.nodo  = NODO_ID;
  llenarEstado(m);
  if (horaValida()) m.flags |= FL_HORA_VALIDA;
  esp_now_send(centralConocida ? macCentral : MAC_BROADCAST, (uint8_t *)&m, sizeof(m));
}

// Llamar en cada vuelta de loop()
static void atenderComunicacion() {
  PaqueteRx p;
  while (xQueueReceive(colaRx, &p, 0) == pdTRUE) {
    if (!centralConocida || memcmp(macCentral, p.mac, 6) != 0) {
      memcpy(macCentral, p.mac, 6);
      agregarPeer(macCentral);
      centralConocida = true;
      Serial.printf("[ESP-NOW] Central encontrada: %02X:%02X:%02X:%02X:%02X:%02X\n",
                    p.mac[0], p.mac[1], p.mac[2], p.mac[3], p.mac[4], p.mac[5]);
      enviarEstado();
    }
    ultimoContactoCentral = millis();

    if (p.m.tipo == MSG_TIEMPO && p.m.epoch > EPOCH_MINIMO) {
      struct timeval tv = {(time_t)p.m.epoch, 0};
      settimeofday(&tv, nullptr);
    } else if (p.m.tipo == MSG_COMANDO && p.m.nodo == NODO_ID) {
      Serial.printf("[APP] Comando %u (sub %u)\n", p.m.comando, p.m.sub);
      aplicarComando(p.m.comando, p.m.sub);
      enviarEstado();
    }
  }

  static unsigned long ultimoReporte = 0;
  if (millis() - ultimoReporte >= INTERVALO_REPORTE_MS) {
    ultimoReporte = millis();
    enviarEstado();
  }

  // Si se pierde la central (reinicio del router, cambio de canal...) se re-escanea
  static unsigned long ultimoEscaneo = 0;
  if (millis() - ultimoContactoCentral > TIEMPO_SIN_CENTRAL_MS &&
      millis() - ultimoEscaneo > TIEMPO_SIN_CENTRAL_MS) {
    ultimoEscaneo = millis();
    centralConocida = false;
    canalActual = buscarCanal();
    fijarCanal(canalActual);
  }
}

// ---------- Buzzer (intermitente, no bloqueante) ----------
static void buzzerIniciar() {
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, !BUZZER_NIVEL_ACTIVO);
}
static void buzzerActualizar(bool alarma, uint16_t periodoMs = 400) {
  bool on = alarma && ((millis() / periodoMs) % 2 == 0);
  digitalWrite(PIN_BUZZER, on ? BUZZER_NIVEL_ACTIVO : !BUZZER_NIVEL_ACTIVO);
}

// ---------- Botón local (BOOT = GPIO0) para silenciar en sitio ----------
static bool botonPresionado() {
  static int anterior = HIGH;
  static unsigned long t = 0;
  int v = digitalRead(PIN_BOTON);
  bool presionado = false;
  if (v != anterior && millis() - t > 50) {
    t = millis();
    if (v == LOW) presionado = true;
    anterior = v;
  }
  return presionado;
}
