#include <Arduino.h>   // debe ir primero: define uint8_t, uint32_t, etc.
// =====================================================================
//  NODO 1 — PUERTA DE ENTRADA  +  CENTRAL (GATEWAY) ESP-NOW  +  APP WEB
//  ESP32 + sensor PIR (HC-SR501) + módulo buzzer
//
//  Funciones:
//   * Puerta: si hay movimiento durante la madrugada (00:00-06:00) y la
//     vigilancia está activada -> alarma. Activable/desactivable desde la app.
//   * Central: recibe por ESP-NOW el estado de los otros 4 nodos, les envía
//     la hora y los comandos de la app.
//   * App: sirve la aplicación web (celular / PC) en http://alarma.local
//     o en la IP que muestra el monitor serie.
//
//   * Acceso remoto: publica el estado en un servidor MQTT en la nube
//     (HiveMQ Cloud) y recibe desde ahí los comandos de la app remota.
//   * Notificaciones: envía cada alarma por Telegram (llega al celular
//     aunque la app esté cerrada) y repite un recordatorio cada 5 min
//     mientras la alarma no se silencie.
//
//  Si no logra conectarse al router crea su propia red "AlarmaCasa"
//  (clave: cuidador123) y la app queda en http://192.168.4.1
//  (en ese modo no hay acceso remoto ni Telegram: no hay internet).
//
//  Librería extra: PubSubClient (Nick O'Leary)
// =====================================================================

// ------------------------- CONFIGURACIÓN -----------------------------
const char* WIFI_SSID  = "TU_RED_WIFI";
const char* WIFI_PASS  = "TU_CLAVE_WIFI";
const char* AP_SSID    = "AlarmaCasa";       // red de respaldo (debe coincidir con SSID_AP_CENTRAL de los nodos)
const char* AP_PASS    = "cuidador123";      // mínimo 8 caracteres
const uint8_t AP_CANAL = 1;
const char* NOMBRE_MDNS = "alarma";          // http://alarma.local

#define PIN_PIR             27
#define PIN_BUZZER          26
#define PIN_BOTON           0
#define PIN_LED             2
#define BUZZER_NIVEL_ACTIVO HIGH

const int HORA_INICIO_MADRUGADA = 0;          // 00:00
const int HORA_FIN_MADRUGADA    = 6;          // 06:00
const unsigned long GRACIA_TRAS_SILENCIO_MS = 2UL * 60 * 1000;  // no re-alarmar 2 min tras silenciar
const unsigned long CALENTAMIENTO_PIR       = 60000UL;
const unsigned long NODO_SIN_CONEXION_MS    = 20000UL;          // nodo "sin conexión" tras 20 s sin datos
const unsigned long INTERVALO_TIEMPO_MS     = 15000UL;          // envío de hora/latido a los nodos

// ---------------- ACCESO REMOTO (MQTT - HiveMQ Cloud) ----------------
#define USAR_MQTT 1
const char* MQTT_HOST = "xxxxxxxxxxxxxxxx.s1.eu.hivemq.cloud";  // "Cluster URL" de HiveMQ
const int   MQTT_PUERTO = 8883;                                  // TLS
const char* MQTT_USUARIO = "central";                            // credencial creada en HiveMQ
const char* MQTT_CLAVE   = "CLAVE_DE_LA_CENTRAL";
const char* ID_CASA      = "casa-cambia-esto-7k2q";  // identificador único; el mismo se pone en la app
const unsigned long INTERVALO_PUBLICACION_MS = 5000UL;

// ---------------- NOTIFICACIONES (TELEGRAM) ----------------
#define USAR_TELEGRAM 1
const char* TELEGRAM_TOKEN   = "1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"; // de @BotFather
const char* TELEGRAM_CHAT_ID = "123456789";          // tu chat o el del grupo de cuidadores (empieza por -)
const char* URL_APP_REMOTA   = "";                   // opcional: https://usuario.github.io/alarma/
const unsigned long RECORDATORIO_MS = 5UL * 60 * 1000;  // repetir aviso mientras siga la alarma
// ---------------------------------------------------------------------

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <Preferences.h>
#include <sys/time.h>
#include <time.h>
#include <stdarg.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include "protocolo.h"
#include "app_web.h"

static const uint8_t MAC_BROADCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

WebServer server(80);
Preferences prefs;
bool modoRouter = false;
wifi_interface_t interfazEspNow = WIFI_IF_STA;

// =====================================================================
//              TELEGRAM (tarea aparte para no bloquear el loop)
// =====================================================================
struct MsgTelegram { char texto[400]; };
QueueHandle_t colaTelegram = nullptr;

void encolarTelegram(const char* texto) {
#if USAR_TELEGRAM
  if (!modoRouter || colaTelegram == nullptr) return;
  MsgTelegram m;
  snprintf(m.texto, sizeof(m.texto), "%s", texto);
  if (xQueueSend(colaTelegram, &m, 0) != pdTRUE) Serial.println("[Telegram] cola llena");
#endif
}

#if USAR_TELEGRAM
String escaparJson(const char* s) {
  String r;
  for (; *s; s++) {
    if (*s == '"' || *s == '\\') { r += '\\'; r += *s; }
    else if (*s == '\n') r += "\\n";
    else r += *s;
  }
  return r;
}

void tareaTelegram(void*) {
  WiFiClientSecure cliente;
  cliente.setInsecure();   // ver README: se puede fijar el certificado raíz
  MsgTelegram m;
  for (;;) {
    if (xQueueReceive(colaTelegram, &m, portMAX_DELAY) != pdTRUE) continue;
    for (int intento = 0; intento < 5; intento++) {
      if (WiFi.status() != WL_CONNECTED) { vTaskDelay(pdMS_TO_TICKS(5000)); continue; }
      HTTPClient http;
      String url = String("https://api.telegram.org/bot") + TELEGRAM_TOKEN + "/sendMessage";
      int codigo = -1;
      if (http.begin(cliente, url)) {
        http.addHeader("Content-Type", "application/json");
        String cuerpo = String("{\"chat_id\":\"") + TELEGRAM_CHAT_ID + "\",\"text\":\"" + escaparJson(m.texto) + "\"}";
        codigo = http.POST(cuerpo);
        http.end();
      }
      if (codigo == 200) break;
      Serial.printf("[Telegram] error %d, reintentando\n", codigo);
      vTaskDelay(pdMS_TO_TICKS(3000));
    }
  }
}
#endif

void iniciarTelegram() {
#if USAR_TELEGRAM
  if (!modoRouter) return;
  colaTelegram = xQueueCreate(12, sizeof(MsgTelegram));
  xTaskCreatePinnedToCore(tareaTelegram, "telegram", 12288, nullptr, 1, nullptr, 0);
#endif
}

// ------------------------- Estado de los nodos ------------------------
struct Nodo {
  const char* nombre;
  bool visto;
  bool enLinea;
  uint8_t mac[6];
  unsigned long ultimoVisto;
  Mensaje est;
};
Nodo nodos[TOTAL_NODOS] = {
  {"Puerta de entrada"}, {"Habitación"}, {"Baño"}, {"Cocina · agua"}, {"Cocina · gas"}
};

// ------------------------- Registro de eventos ------------------------
#define MAX_EVENTOS 30
struct Evento { char hora[20]; char texto[96]; bool alarma; };
Evento eventos[MAX_EVENTOS];
int nEventos = 0, idxEvento = 0;

bool horaValida() { return time(nullptr) > (time_t)EPOCH_MINIMO; }

void textoHora(char* buf, size_t n, const char* formato) {
  if (horaValida()) {
    time_t ahora = time(nullptr);
    struct tm t;
    localtime_r(&ahora, &t);
    strftime(buf, n, formato, &t);
  } else {
    snprintf(buf, n, "+%lus", millis() / 1000);
  }
}

void registrarEvento(bool esAlarma, const char* fmt, ...) {
  Evento &e = eventos[idxEvento];
  textoHora(e.hora, sizeof(e.hora), "%d/%m %H:%M:%S");
  va_list args;
  va_start(args, fmt);
  vsnprintf(e.texto, sizeof(e.texto), fmt, args);
  va_end(args);
  e.alarma = esAlarma;
  idxEvento = (idxEvento + 1) % MAX_EVENTOS;
  if (nEventos < MAX_EVENTOS) nEventos++;
  Serial.printf("[EVENTO] %s  %s\n", e.hora, e.texto);

  // Telegram: alarmas, pérdidas/recuperaciones de conexión y silenciados
  if (esAlarma || strstr(e.texto, "silenci") || strstr(e.texto, "reconectado")) {
    char msg[300];
    const char* emoji = esAlarma ? "🚨" : (strstr(e.texto, "silenci") ? "🔕" : "✅");
    if (URL_APP_REMOTA[0])
      snprintf(msg, sizeof(msg), "%s %s\n%s\n%s", emoji, e.texto, e.hora, URL_APP_REMOTA);
    else
      snprintf(msg, sizeof(msg), "%s %s\n%s", emoji, e.texto, e.hora);
    encolarTelegram(msg);
  }
}

// Mientras haya alarmas sin silenciar, recuerda por Telegram cada RECORDATORIO_MS
void revisarRecordatorios() {
  static unsigned long ultimo = 0;
  char msg[300];
  int n = snprintf(msg, sizeof(msg), "⏰ Siguen activas sin silenciar:");
  bool hay = false;
  for (int i = 0; i < TOTAL_NODOS; i++) {
    if (nodos[i].est.alarmas) {
      hay = true;
      n += snprintf(msg + n, sizeof(msg) - n, "\n• %s", nodos[i].nombre);
    }
  }
  if (!hay) { ultimo = millis(); return; }
  if (millis() - ultimo >= RECORDATORIO_MS) {
    ultimo = millis();
    encolarTelegram(msg);
  }
}

// Genera eventos cuando aparece una alarma nueva en un nodo
void revisarAlarmasNuevas(uint8_t id, uint8_t antes, const Mensaje &m) {
  uint8_t nuevas = m.alarmas & ~antes;
  const char* n = nodos[id].nombre;
  if (nuevas & AL_INTRUSION)      registrarEvento(true, "ALARMA %s: movimiento en la madrugada", n);
  if (nuevas & AL_SIN_MOVIMIENTO) registrarEvento(true, "ALARMA %s: sin movimiento por %lu min", n,
                                                 (unsigned long)((id == NODO_COCINA_GAS ? m.limite2 : m.limite) / 60));
  if (nuevas & AL_AGUA)           registrarEvento(true, "ALARMA %s: agua corriendo más de %lu min", n, (unsigned long)(m.limite / 60));
  if (nuevas & AL_GAS)            registrarEvento(true, "ALARMA %s: gas detectado más de %lu min", n, (unsigned long)(m.limite / 60));
  if (nuevas & AL_TEMPERATURA)    registrarEvento(true, "ALARMA %s: temperatura %.1f °C", n, m.valor1);
}

// =====================================================================
//                              ESP-NOW
// =====================================================================
struct PaqueteRx { uint8_t mac[6]; Mensaje m; };
QueueHandle_t colaRx;

void encolarRx(const uint8_t* mac, const uint8_t* data, int len) {
  if (len != (int)sizeof(Mensaje)) return;
  PaqueteRx p;
  memcpy(p.mac, mac, 6);
  memcpy(&p.m, data, sizeof(Mensaje));
  if (p.m.magic != ESPNOW_MAGIC || p.m.tipo != MSG_ESTADO) return;
  if (p.m.nodo == NODO_PUERTA || p.m.nodo >= TOTAL_NODOS) return;
  xQueueSend(colaRx, &p, 0);
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
void alRecibirEspNow(const esp_now_recv_info_t* info, const uint8_t* data, int len) { encolarRx(info->src_addr, data, len); }
#else
void alRecibirEspNow(const uint8_t* mac, const uint8_t* data, int len) { encolarRx(mac, data, len); }
#endif

void agregarPeer(const uint8_t* mac) {
  if (esp_now_is_peer_exist(mac)) return;
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, mac, 6);
  peer.channel = 0;
  peer.ifidx   = interfazEspNow;
  peer.encrypt = false;
  esp_now_add_peer(&peer);
}

void iniciarEspNow() {
  colaRx = xQueueCreate(20, sizeof(PaqueteRx));
  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESP-NOW] Error al iniciar, reiniciando...");
    delay(2000);
    ESP.restart();
  }
  esp_now_register_recv_cb(alRecibirEspNow);
  agregarPeer(MAC_BROADCAST);
  uint8_t canal; wifi_second_chan_t sec;
  esp_wifi_get_channel(&canal, &sec);
  Serial.printf("[ESP-NOW] Central lista en canal %u\n", canal);
}

void atenderEspNow() {
  PaqueteRx p;
  while (xQueueReceive(colaRx, &p, 0) == pdTRUE) {
    Nodo &n = nodos[p.m.nodo];
    if (!n.visto || memcmp(n.mac, p.mac, 6) != 0) {
      memcpy(n.mac, p.mac, 6);
      agregarPeer(n.mac);
      n.visto = true;
      registrarEvento(false, "%s conectado", n.nombre);
    } else if (!n.enLinea) {
      registrarEvento(false, "%s reconectado", n.nombre);
    }
    revisarAlarmasNuevas(p.m.nodo, n.est.alarmas, p.m);
    n.est = p.m;
    n.enLinea = true;
    n.ultimoVisto = millis();
  }
}

void enviarTiempo() {
  Mensaje m;
  memset(&m, 0, sizeof(m));
  m.magic = ESPNOW_MAGIC;
  m.tipo  = MSG_TIEMPO;
  m.epoch = horaValida() ? (uint32_t)time(nullptr) : 0;   // también es el latido de la central
  esp_now_send(MAC_BROADCAST, (uint8_t*)&m, sizeof(m));
}

void revisarConexiones() {
  for (int i = 1; i < TOTAL_NODOS; i++) {
    Nodo &n = nodos[i];
    if (n.visto && n.enLinea && millis() - n.ultimoVisto > NODO_SIN_CONEXION_MS) {
      n.enLinea = false;
      registrarEvento(true, "%s perdió la conexión", n.nombre);
    }
  }
}

// =====================================================================
//                          NODO PUERTA (local)
// =====================================================================
bool puertaHabilitada = true;
uint8_t puertaAlarmas = 0;
bool puertaMovimiento = false;
unsigned long ultimoSilencioPuerta = 0;
bool puertaSilenciadaAlgunaVez = false;

bool esMadrugada() {
  if (!horaValida()) return false;
  time_t ahora = time(nullptr);
  struct tm t;
  localtime_r(&ahora, &t);
  if (HORA_INICIO_MADRUGADA < HORA_FIN_MADRUGADA)
    return t.tm_hour >= HORA_INICIO_MADRUGADA && t.tm_hour < HORA_FIN_MADRUGADA;
  return t.tm_hour >= HORA_INICIO_MADRUGADA || t.tm_hour < HORA_FIN_MADRUGADA;
}

void comandoPuerta(uint8_t cmd) {
  switch (cmd) {
    case CMD_ACTIVAR:    puertaHabilitada = true;  prefs.putBool("hab", true);  break;
    case CMD_DESACTIVAR: puertaHabilitada = false; prefs.putBool("hab", false); puertaAlarmas = 0; break;
    case CMD_SILENCIAR:
      puertaAlarmas = 0;
      ultimoSilencioPuerta = millis();
      puertaSilenciadaAlgunaVez = true;
      break;
  }
}

void logicaPuerta() {
  puertaMovimiento = (millis() > CALENTAMIENTO_PIR) && digitalRead(PIN_PIR) == HIGH;
  bool madrugada = esMadrugada();
  bool enGracia = puertaSilenciadaAlgunaVez && (millis() - ultimoSilencioPuerta < GRACIA_TRAS_SILENCIO_MS);

  if (puertaHabilitada && madrugada && puertaMovimiento && !enGracia && !(puertaAlarmas & AL_INTRUSION)) {
    puertaAlarmas |= AL_INTRUSION;
  }

  // Se refleja como un nodo más para la app
  Nodo &n = nodos[NODO_PUERTA];
  Mensaje m;
  memset(&m, 0, sizeof(m));
  m.nodo       = NODO_PUERTA;
  m.habilitado = puertaHabilitada ? HAB_PRINCIPAL : 0;
  m.alarmas    = puertaAlarmas;
  m.movimiento = puertaMovimiento;
  if (madrugada)                        m.flags |= FL_MADRUGADA;
  if (horaValida())                     m.flags |= FL_HORA_VALIDA;
  if (millis() < CALENTAMIENTO_PIR)     m.flags |= FL_CALENTANDO;
  revisarAlarmasNuevas(NODO_PUERTA, n.est.alarmas, m);
  n.est = m;
  n.visto = n.enLinea = true;
  n.ultimoVisto = millis();

  bool on = puertaAlarmas && ((millis() / 250) % 2 == 0);
  digitalWrite(PIN_BUZZER, on ? BUZZER_NIVEL_ACTIVO : !BUZZER_NIVEL_ACTIVO);
}


// =====================================================================
//                    Comandos (app local, app remota, botón)
// =====================================================================
bool enviarComando(uint8_t id, uint8_t cmd, uint8_t sub) {
  if (id >= TOTAL_NODOS) return false;
  if (id == NODO_PUERTA) { comandoPuerta(cmd); return true; }
  Nodo &n = nodos[id];
  if (!n.visto) return false;
  Mensaje m;
  memset(&m, 0, sizeof(m));
  m.magic   = ESPNOW_MAGIC;
  m.tipo    = MSG_COMANDO;
  m.nodo    = id;
  m.comando = cmd;
  m.sub     = sub;
  return esp_now_send(n.mac, (uint8_t*)&m, sizeof(m)) == ESP_OK;
}

// accion: "activar" | "desactivar" | "silenciar". origen: texto para el historial.
// Devuelve 1 = ok, 0 = nodo sin conexión, -1 = petición inválida
int ejecutarComando(int id, const char* accion, uint8_t sub, const char* origen) {
  uint8_t cmd = !strcmp(accion, "activar")    ? CMD_ACTIVAR
              : !strcmp(accion, "desactivar") ? CMD_DESACTIVAR
              : !strcmp(accion, "silenciar")  ? CMD_SILENCIAR : 0;
  if (!cmd || id < 0 || id >= TOTAL_NODOS) return -1;
  if (!enviarComando(id, cmd, sub)) return 0;
  const char* verbo = cmd == CMD_ACTIVAR ? "activó" : cmd == CMD_DESACTIVAR ? "desactivó" : "silenció";
  registrarEvento(false, "%s %s %s%s", origen, verbo, nodos[id].nombre,
                  (id == NODO_COCINA_GAS && sub == 1) ? " (presencia)" : "");
  return 1;
}

void silenciarTodo(const char* origen) {
  for (int i = 0; i < TOTAL_NODOS; i++)
    if (nodos[i].est.alarmas) enviarComando(i, CMD_SILENCIAR, 0);
  registrarEvento(false, "%s silenció todas las alarmas", origen);
}

// ---------------------------------------------------------------------
//  JSON del estado completo (lo usan la app local y la app remota)
// ---------------------------------------------------------------------
String jsonEstado(int maxEventos) {
  String j;
  j.reserve(6144);
  char hora[24];
  textoHora(hora, sizeof(hora), "%d/%m/%Y %H:%M:%S");
  j += "{\"hora\":\""; j += hora;
  j += "\",\"horaValida\":"; j += horaValida() ? "true" : "false";
  j += ",\"red\":\""; j += modoRouter ? "wifi" : "ap";
  j += "\",\"nodos\":[";
  for (int i = 0; i < TOTAL_NODOS; i++) {
    Nodo &n = nodos[i];
    Mensaje &m = n.est;
    char buf[400];
    snprintf(buf, sizeof(buf),
      "%s{\"id\":%d,\"nombre\":\"%s\",\"visto\":%s,\"enLinea\":%s,\"hab\":%u,\"al\":%u,\"mov\":%u,"
      "\"fl\":%u,\"c1\":%lu,\"l1\":%lu,\"c2\":%lu,\"l2\":%lu,\"v1\":%.2f,\"v2\":%.0f,\"hace\":%lu}",
      i ? "," : "", i, n.nombre, n.visto ? "true" : "false", n.enLinea ? "true" : "false",
      m.habilitado, m.alarmas, m.movimiento, m.flags,
      (unsigned long)m.contador, (unsigned long)m.limite, (unsigned long)m.contador2, (unsigned long)m.limite2,
      m.valor1, m.valor2, n.visto ? (millis() - n.ultimoVisto) / 1000 : 0UL);
    j += buf;
  }
  j += "],\"eventos\":[";
  int total = nEventos < maxEventos ? nEventos : maxEventos;
  for (int k = 0; k < total; k++) {
    int idx = (idxEvento - 1 - k + MAX_EVENTOS) % MAX_EVENTOS;   // más reciente primero
    if (k) j += ",";
    j += "{\"t\":\""; j += eventos[idx].hora;
    j += "\",\"x\":\""; j += eventos[idx].texto;
    j += "\",\"a\":"; j += eventos[idx].alarma ? "true" : "false";
    j += "}";
  }
  j += "]}";
  return j;
}

// =====================================================================
//                 ACCESO REMOTO: MQTT sobre TLS (HiveMQ Cloud)
//   casa/<ID_CASA>/estado  <- JSON del estado (retenido)
//   casa/<ID_CASA>/online  <- "1" / "0" (último deseo si se cae la central)
//   casa/<ID_CASA>/cmd     -> "nodo:accion:sub"  o  "todo:silenciar"
// =====================================================================
#if USAR_MQTT
WiFiClientSecure clienteTlsMqtt;
PubSubClient mqtt(clienteTlsMqtt);
char topicoEstado[80], topicoOnline[80], topicoCmd[80];

void procesarComandoRemoto(const char* texto) {
  char buf[48];
  snprintf(buf, sizeof(buf), "%s", texto);
  char* a = strtok(buf, ":");
  char* b = strtok(nullptr, ":");
  char* c = strtok(nullptr, ":");
  if (!a || !b) return;
  if (!strcmp(a, "todo") && !strcmp(b, "silenciar")) silenciarTodo("App remota:");
  else ejecutarComando(atoi(a), b, c ? atoi(c) : 0, "App remota:");
}

void alRecibirMqtt(char* topico, byte* payload, unsigned int len) {
  char texto[48];
  if (len >= sizeof(texto)) len = sizeof(texto) - 1;
  memcpy(texto, payload, len);
  texto[len] = 0;
  Serial.printf("[MQTT] comando: %s\n", texto);
  procesarComandoRemoto(texto);
}

void iniciarMqtt() {
  snprintf(topicoEstado, sizeof(topicoEstado), "casa/%s/estado", ID_CASA);
  snprintf(topicoOnline, sizeof(topicoOnline), "casa/%s/online", ID_CASA);
  snprintf(topicoCmd,    sizeof(topicoCmd),    "casa/%s/cmd",    ID_CASA);
  clienteTlsMqtt.setInsecure();                 // ver README: se puede fijar el certificado raíz
  mqtt.setServer(MQTT_HOST, MQTT_PUERTO);
  mqtt.setCallback(alRecibirMqtt);
  mqtt.setBufferSize(6144);
  mqtt.setKeepAlive(30);
}

// Resumen de lo importante: si cambia, se publica en el acto (no se espera 5 s)
uint32_t firmaEstado() {
  uint32_t f = nEventos * 131u + idxEvento;
  for (int i = 0; i < TOTAL_NODOS; i++)
    f = f * 31u + nodos[i].est.alarmas * 7u + nodos[i].est.habilitado * 3u + nodos[i].enLinea;
  return f;
}

void atenderMqtt() {
  if (!modoRouter || WiFi.status() != WL_CONNECTED) return;
  if (!mqtt.connected()) {
    static unsigned long ultimoIntento = 0;
    static bool estuvoConectado = false;
    if (estuvoConectado) { estuvoConectado = false; Serial.println("[MQTT] desconectado"); }
    if (ultimoIntento && millis() - ultimoIntento < 10000) return;
    ultimoIntento = millis();
    char idCliente[64];
    snprintf(idCliente, sizeof(idCliente), "central-%s", ID_CASA);
    Serial.println("[MQTT] conectando...");
    if (mqtt.connect(idCliente, MQTT_USUARIO, MQTT_CLAVE, topicoOnline, 1, true, "0")) {
      estuvoConectado = true;
      mqtt.publish(topicoOnline, "1", true);
      mqtt.subscribe(topicoCmd, 1);
      Serial.println("[MQTT] conectado");
    } else {
      Serial.printf("[MQTT] fallo rc=%d (revisa host, usuario y clave)\n", mqtt.state());
    }
    return;
  }
  mqtt.loop();

  static unsigned long ultimaPublicacion = 0;
  static uint32_t firmaAnterior = 0;
  uint32_t firma = firmaEstado();
  if (firma != firmaAnterior || millis() - ultimaPublicacion >= INTERVALO_PUBLICACION_MS) {
    firmaAnterior = firma;
    ultimaPublicacion = millis();
    String j = jsonEstado(15);
    if (!mqtt.publish(topicoEstado, j.c_str(), true)) Serial.println("[MQTT] no se pudo publicar");
  }
}
#else
void iniciarMqtt() {}
void atenderMqtt() {}
#endif

// =====================================================================
//                         Servidor web (app local)
// =====================================================================
void responderJson(int codigo, const String &json) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(codigo, "application/json; charset=utf-8", json);
}

void handleEstado() { responderJson(200, jsonEstado(MAX_EVENTOS)); }

void handleComando() {
  if (!server.hasArg("nodo") || !server.hasArg("accion")) { responderJson(400, "{\"ok\":false}"); return; }
  int r = ejecutarComando(server.arg("nodo").toInt(), server.arg("accion").c_str(),
                          server.hasArg("sub") ? server.arg("sub").toInt() : 0, "App (casa):");
  if (r == 1)      responderJson(200, "{\"ok\":true}");
  else if (r == 0) responderJson(503, "{\"ok\":false,\"error\":\"nodo sin conexión\"}");
  else             responderJson(400, "{\"ok\":false}");
}

void handleSilenciarTodo() {
  silenciarTodo("App (casa):");
  responderJson(200, "{\"ok\":true}");
}

// El celular envía su hora al abrir la app: útil si no hay internet (modo AP)
void handleHora() {
  if (!horaValida() && server.hasArg("epoch")) {
    uint32_t e = strtoul(server.arg("epoch").c_str(), nullptr, 10);
    if (e > EPOCH_MINIMO) {
      struct timeval tv = {(time_t)e, 0};
      settimeofday(&tv, nullptr);
      registrarEvento(false, "Hora ajustada desde la app");
      enviarTiempo();
    }
  }
  responderJson(200, "{\"ok\":true}");
}

void iniciarServidor() {
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html; charset=utf-8", APP_HTML); });
  server.on("/api/estado", HTTP_GET, handleEstado);
  server.on("/api/cmd", handleComando);
  server.on("/api/silenciar_todo", handleSilenciarTodo);
  server.on("/api/hora", handleHora);
  server.onNotFound([]() { server.send(404, "text/plain", "No encontrado"); });
  server.begin();
}

// =====================================================================
//                               Red
// =====================================================================
void iniciarRed() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("Conectando a %s", WIFI_SSID);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) { delay(500); Serial.print("."); }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    modoRouter = true;
    interfazEspNow = WIFI_IF_STA;
    WiFi.setAutoReconnect(true);
    configTzTime(ZONA_HORARIA, "pool.ntp.org", "time.google.com");
    Serial.printf("WiFi OK. App en: http://%s  (canal %d)\n", WiFi.localIP().toString().c_str(), WiFi.channel());
  } else {
    modoRouter = false;
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS, AP_CANAL);
    interfazEspNow = WIFI_IF_AP;
    setenv("TZ", ZONA_HORARIA, 1);
    tzset();
    Serial.printf("Sin router. Red propia '%s'. App en: http://%s\n", AP_SSID, WiFi.softAPIP().toString().c_str());
  }
  if (MDNS.begin(NOMBRE_MDNS)) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("También en: http://%s.local\n", NOMBRE_MDNS);
  }
}

// =====================================================================
void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, !BUZZER_NIVEL_ACTIVO);

  prefs.begin("central", false);
  puertaHabilitada = prefs.getBool("hab", true);

  iniciarRed();
  iniciarEspNow();
  iniciarServidor();
  iniciarTelegram();
  iniciarMqtt();
  registrarEvento(false, "Central iniciada");
  encolarTelegram("🏠 Central de alarmas encendida");
}

void loop() {
  server.handleClient();
  atenderEspNow();
  logicaPuerta();
  revisarConexiones();
  atenderMqtt();
  revisarRecordatorios();

  static unsigned long tTiempo = 0;
  if (millis() - tTiempo >= INTERVALO_TIEMPO_MS) { tTiempo = millis(); enviarTiempo(); }

  // Botón BOOT: silencia TODAS las alarmas de la casa
  static int botonAnt = HIGH;
  int b = digitalRead(PIN_BOTON);
  if (b != botonAnt) { botonAnt = b; if (b == LOW) { delay(30); silenciarTodo("Botón de la central:"); } }

  // LED: fijo = todo normal, parpadeo rápido = alguna alarma
  bool hayAlarma = false;
  for (int i = 0; i < TOTAL_NODOS; i++) if (nodos[i].est.alarmas) hayAlarma = true;
  digitalWrite(PIN_LED, hayAlarma ? (millis() / 150) % 2 : HIGH);
  delay(5);
}
