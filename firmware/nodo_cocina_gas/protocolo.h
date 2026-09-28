// =====================================================================
//  protocolo.h  —  Protocolo ESP-NOW común a TODAS las ESP32
//  (este archivo debe ser idéntico en las 5 carpetas)
// =====================================================================
#pragma once
#include <Arduino.h>

#define ESPNOW_MAGIC 0xA7          // identifica los paquetes de este sistema

// ---- Tipos de mensaje ----
enum : uint8_t {
  MSG_ESTADO  = 1,   // nodo    -> central : estado periódico / cambios
  MSG_COMANDO = 2,   // central -> nodo    : activar / desactivar / silenciar
  MSG_TIEMPO  = 3    // central -> todos   : hora + latido (sirve para descubrir la central)
};

// ---- Identificadores de nodo ----
enum : uint8_t {
  NODO_PUERTA      = 0,   // central (gateway)
  NODO_HABITACION  = 1,
  NODO_BANO        = 2,
  NODO_COCINA_AGUA = 3,
  NODO_COCINA_GAS  = 4,
  TOTAL_NODOS      = 5
};

// ---- Comandos ----
enum : uint8_t {
  CMD_ACTIVAR    = 1,
  CMD_DESACTIVAR = 2,
  CMD_SILENCIAR  = 3     // apaga la alarma y reinicia los contadores
};

// ---- Bits de alarma ----
#define AL_SIN_MOVIMIENTO 0x01
#define AL_AGUA           0x02
#define AL_GAS            0x04
#define AL_TEMPERATURA    0x08
#define AL_INTRUSION      0x10

// ---- Bits de "habilitado" ----
#define HAB_PRINCIPAL   0x01   // función principal del nodo
#define HAB_SECUNDARIO  0x02   // sólo cocina-gas: vigilancia de presencia (PIR)

// ---- Bits de flags (información extra para la app) ----
#define FL_CONTANDO1        0x01   // contador principal en marcha
#define FL_CONTANDO2        0x02   // contador secundario en marcha (PIR cocina-gas)
#define FL_HORARIO_NOCTURNO 0x04   // habitación: dentro del horario nocturno
#define FL_MADRUGADA        0x08   // puerta: dentro de la madrugada
#define FL_CALENTANDO       0x10   // sensor MQ / PIR calentando
#define FL_ERROR_SENSOR     0x20   // sensor de temperatura no responde
#define FL_HORA_VALIDA      0x40   // el nodo tiene la hora sincronizada

typedef struct __attribute__((packed)) {
  uint8_t  magic;
  uint8_t  tipo;
  uint8_t  nodo;
  uint8_t  habilitado;   // HAB_*
  uint8_t  alarmas;      // AL_*
  uint8_t  movimiento;   // PIR actual (o "hay flujo" en el nodo de agua)
  uint8_t  flags;        // FL_*
  uint8_t  comando;      // CMD_* (sólo MSG_COMANDO)
  uint8_t  sub;          // 0 = principal, 1 = secundario (sólo MSG_COMANDO)
  uint8_t  reservado[3];
  uint32_t contador;     // segundos transcurridos del contador principal
  uint32_t limite;       // límite del contador principal (s)
  uint32_t contador2;    // contador secundario (s)
  uint32_t limite2;      // límite secundario (s)
  float    valor1;       // caudal L/min  |  temperatura °C
  float    valor2;       // lectura del sensor de gas (0-4095)
  uint32_t epoch;        // hora Unix (sólo MSG_TIEMPO)
} Mensaje;

#define ZONA_HORARIA "<-05>5"   // Colombia (UTC-5, sin horario de verano)
#define EPOCH_MINIMO 1700000000UL
