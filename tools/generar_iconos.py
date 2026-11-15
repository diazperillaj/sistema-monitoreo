"""Íconos de la PWA, dibujados aquí para que su origen quede en el repo (§11.5).

El motivo es el del tablero: un techo sobre una escala calibrada, con la aguja en verdín y la
marca del límite en rojo. Fondo grafito a todo el borde (íconos "maskable": lo importante cabe en
el círculo central del 80 %). La insignia de Android es la misma silueta, en blanco y sin fondo.

Uso, desde backend/:
    uv run --with pillow python ../tools/generar_iconos.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
LADO = 512
AUMENTO = 4  # se dibuja 4 veces más grande y se reduce: bordes suaves sin dependencias extra

GRAFITO = "#151a1c"
HUESO = "#e7ecea"
MARCA = "#56636a"
PISTA = "#232b2f"
VERDIN = "#4cc1a2"
ROJO = "#ff5b4f"


def dibujar(color_fondo: str | None, tinta: str, marca: str, pista: str, aguja: str, limite: str):
    t = LADO * AUMENTO
    img = Image.new("RGBA", (t, t), color_fondo or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def p(valor: float) -> int:
        return round(valor * AUMENTO)

    # Techo: una sola línea quebrada, con puntas redondeadas
    grosor = p(30)
    techo = [(p(140), p(246)), (p(256), p(148)), (p(372), p(246))]
    d.line(techo, fill=tinta, width=grosor, joint="curve")
    for x, y in (techo[0], techo[2]):
        d.ellipse((x - grosor / 2, y - grosor / 2, x + grosor / 2, y + grosor / 2), fill=tinta)

    # Escala: marcas finas y los tres escalones más altos
    izquierda, derecha = 150, 350
    for i in range(1, 8):
        x = izquierda + (derecha - izquierda) * i / 8
        alto = 26 if i in (2, 4, 6) else 14
        d.rounded_rectangle((p(x - 3), p(300 - alto), p(x + 3), p(300)), radius=p(3), fill=marca)

    # Pista con la aguja al 60 % y la marca del límite
    d.rounded_rectangle((p(izquierda), p(312), p(derecha), p(344)), radius=p(6), fill=pista)
    d.rounded_rectangle(
        (p(izquierda), p(312), p(izquierda + (derecha - izquierda) * 0.6), p(344)),
        radius=p(6),
        fill=aguja,
    )
    d.rounded_rectangle((p(derecha + 8), p(290), p(derecha + 20), p(366)), radius=p(6), fill=limite)
    return img


def guardar(img: Image.Image, nombre: str, lado: int) -> None:
    img.resize((lado, lado), Image.Resampling.LANCZOS).save(DESTINO / nombre, optimize=True)
    print(f"{nombre}: {lado}×{lado}")


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    icono = dibujar(GRAFITO, HUESO, MARCA, PISTA, VERDIN, ROJO)
    guardar(icono, "icon-512.png", 512)
    guardar(icono, "icon-192.png", 192)
    guardar(icono, "apple-touch-icon.png", 180)
    # Insignia de Android: solo cuenta el canal alfa, así que todo va en blanco
    blanco = "#ffffff"
    insignia = dibujar(None, blanco, blanco, (255, 255, 255, 90), blanco, blanco)
    guardar(insignia, "badge-96.png", 96)
