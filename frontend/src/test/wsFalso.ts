/**
 * Un WebSocket de mentira para las pruebas: la prueba decide cuándo se abre, qué mensajes
 * llegan y cuándo se corta, sin red de por medio.
 */
export class WsFalso {
  static instancias: WsFalso[] = [];

  static ultima(): WsFalso {
    const ultima = WsFalso.instancias.at(-1);
    if (!ultima) throw new Error("No se abrió ningún WebSocket");
    return ultima;
  }

  static reiniciar() {
    WsFalso.instancias = [];
  }

  readonly url: string;
  enviados: string[] = [];
  cerrado = false;
  onopen: (() => void) | null = null;
  onmessage: ((evento: { data: string }) => void) | null = null;
  onclose: ((evento: { code: number }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    WsFalso.instancias.push(this);
  }

  send(datos: string) {
    this.enviados.push(datos);
  }

  close(codigo = 1000) {
    if (this.cerrado) return;
    this.cerrado = true;
    this.onclose?.({ code: codigo });
  }

  // ---- lo que hace el servidor
  abrir() {
    this.onopen?.();
  }

  recibir(mensaje: unknown) {
    this.onmessage?.({ data: JSON.stringify(mensaje) });
  }

  cortar(codigo = 1006) {
    this.close(codigo);
  }
}
