import { describe, expect, it } from "vitest";
import { AL, FL, HAB, nodo } from "../test/datos";
import { distintivo, instrumento, lecturaEnVivo, type Escala } from "./instrumento";

describe("distintivo: primero lo que impide saber, luego la alarma", () => {
  it.each([
    ["esperando", nodo(2, { visto: false, al: AL.SIN_MOVIMIENTO })],
    ["sin_conexion", nodo(2, { enLinea: false, al: AL.SIN_MOVIMIENTO })],
    ["alarma", nodo(2, { al: AL.SIN_MOVIMIENTO, hab: 0 })],
    ["desactivado", nodo(2, { hab: 0 })],
    ["vigilando", nodo(2)],
  ])("%s", (esperado, n) => {
    expect(distintivo(n)).toBe(esperado);
  });
});

describe("instrumento de cada nodo", () => {
  it("puerta: sin escala, con horario y el interruptor de madrugada", () => {
    const i = instrumento(nodo(0, { fl: FL.HORA_VALIDA | FL.MADRUGADA }));
    expect(i.escalas).toEqual([]);
    expect(i.datos).toContainEqual({ etiqueta: "Horario", valor: "Madrugada: vigilando" });
    expect(i.interruptores).toEqual([
      { sub: 0, etiqueta: "Vigilancia de madrugada", activo: true },
    ]);
  });

  it("puerta sin hora sincronizada: lo avisa como problema del sensor", () => {
    const i = instrumento(nodo(0, { fl: 0 }));
    expect(i.datos).toContainEqual({
      etiqueta: "Horario",
      valor: "Hora no sincronizada",
      aviso: true,
    });
  });

  it("habitación pausada de noche: lo dice así, no 'Desactivado'", () => {
    const i = instrumento(nodo(1, { hab: 0, fl: FL.HORA_VALIDA | FL.HORARIO_NOCTURNO }));
    expect(i.distintivo).toBe("desactivado");
    expect(i.texto).toBe("En pausa por la noche");
    expect(i.escalas).toEqual([]); // sin vigilancia no hay contador
  });

  it("baño contando: la escala con su valor y su límite", () => {
    const i = instrumento(nodo(2, { fl: FL.HORA_VALIDA | FL.CONTANDO1, c1: 125 }));
    expect(i.escalas).toEqual([
      expect.objectContaining({
        etiqueta: "Sin movimiento",
        valor: 125,
        limite: 600,
        contando: true,
      }),
    ]);
  });

  it("cocina · gas: dos interruptores y la segunda escala solo con presencia", () => {
    const sinPresencia = instrumento(nodo(4));
    expect(sinPresencia.interruptores.map((x) => x.etiqueta)).toEqual([
      "Gas y temperatura",
      "Presencia (inactividad)",
    ]);
    expect(sinPresencia.escalas.map((e) => e.etiqueta)).toEqual(["Gas detectado"]);

    const conPresencia = instrumento(nodo(4, { hab: HAB.PRINCIPAL | HAB.SECUNDARIO }));
    expect(conPresencia.interruptores[1].activo).toBe(true);
    expect(conPresencia.escalas.map((e) => e.etiqueta)).toEqual([
      "Gas detectado",
      "Sin movimiento",
    ]);
  });

  it("cocina · gas con el sensor de temperatura dañado", () => {
    const i = instrumento(nodo(4, { fl: FL.HORA_VALIDA | FL.ERROR_SENSOR }));
    expect(i.datos[0]).toEqual({ etiqueta: "Temperatura", valor: "Error de sensor", aviso: true });
  });

  it("nodo que nunca se conectó: solo la ayuda", () => {
    const i = instrumento(nodo(3, { visto: false }));
    expect(i.texto).toBe("Esperando nodo");
    expect(i.ayuda).toMatch(/Enciende este nodo/);
    expect(i.escalas).toEqual([]);
  });
});

describe("batería de cada nodo", () => {
  const bateria = (bat: number, bfl: number) =>
    instrumento(nodo(2, { bat, bfl, bv: 3.9 })).datos.find((d) => d.etiqueta === "Batería");

  it("sin batería (firmware anterior) no se muestra", () => {
    expect(instrumento(nodo(2)).datos.some((d) => d.etiqueta === "Batería")).toBe(false);
  });

  it("el porcentaje y qué hacer en cada caso", () => {
    expect(bateria(64, 0x01)).toEqual({ etiqueta: "Batería", valor: "64 %" });
    expect(bateria(71, 0x03)).toEqual({ etiqueta: "Batería", valor: "71 % · cargando" });
    expect(bateria(100, 0x0b)).toEqual({
      etiqueta: "Batería",
      valor: "100 % · desconecta el cargador",
    });
    // Ya desconectada, la marca de llena sigue un rato: no se le pide desconectar otra vez
    expect(bateria(100, 0x09)).toEqual({ etiqueta: "Batería", valor: "100 %" });
  });

  it("baja: con el ícono de aviso, no como alarma", () => {
    expect(bateria(9, 0x05)).toEqual({
      etiqueta: "Batería",
      valor: "9 % · ponla a cargar",
      aviso: true,
    });
    expect(instrumento(nodo(2, { bat: 9, bfl: 0x05 })).distintivo).toBe("vigilando");
  });
});

describe("lecturaEnVivo: el contador avanza entre reportes sin pasar el límite", () => {
  const escala: Escala = {
    etiqueta: "Sin movimiento",
    valor: 100,
    limite: 600,
    contando: true,
    enAlarma: false,
    enReposo: "",
  };

  it("suma la antigüedad del dato y lo que pasó desde que llegó", () => {
    expect(lecturaEnVivo(escala, { antiguedadS: 3, segundosDesdeLlegada: 7, enVivo: true })).toBe(
      110,
    );
  });

  it("nunca pasa del límite", () => {
    expect(
      lecturaEnVivo(escala, { antiguedadS: 0, segundosDesdeLlegada: 9000, enVivo: true }),
    ).toBe(600);
  });

  it("sin datos en vivo, se queda en lo último que reportó la central", () => {
    expect(
      lecturaEnVivo(escala, { antiguedadS: 30, segundosDesdeLlegada: 30, enVivo: false }),
    ).toBe(100);
  });

  it("si no cuenta, marca cero; si ya sonó, el límite", () => {
    const opciones = { antiguedadS: 0, segundosDesdeLlegada: 5, enVivo: true };
    expect(lecturaEnVivo({ ...escala, contando: false }, opciones)).toBe(0);
    expect(lecturaEnVivo({ ...escala, contando: false, enAlarma: true }, opciones)).toBe(600);
  });
});
