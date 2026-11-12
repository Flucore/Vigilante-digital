"""Prepara los clips del conjunto de validación.

Recorta la mitad RGB de los videos compuestos (profundidad + RGB lado a lado)
y escala todo a una resolución uniforme. Los videos que ya vienen solo en RGB
se escalan sin recortar.

Uso:
    python preparar_clips.py <carpeta_origen> <carpeta_destino>
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

ANCHO_SALIDA = 640
ALTO_SALIDA = 480
EXTENSIONES = {".mp4", ".avi", ".mov", ".mkv"}


def es_compuesto(ancho: int, alto: int) -> bool:
    """True si el frame parece dos imágenes 4:3 pegadas lado a lado."""
    if alto <= 0:
        return False
    proporcion = ancho / alto
    # Una sola imagen 4:3 da 1.33; dos pegadas dan 2.67.
    return proporcion > 2.0


def procesar(origen: Path, destino: Path) -> tuple[str, int]:
    cap = cv2.VideoCapture(str(origen))
    if not cap.isOpened():
        raise RuntimeError(f"no se pudo abrir {origen.name}")

    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    compuesto = es_compuesto(ancho, alto)
    x0 = ancho // 2 if compuesto else 0
    ancho_util = ancho - x0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(destino), fourcc, fps, (ANCHO_SALIDA, ALTO_SALIDA))
    if not out.isOpened():
        cap.release()
        raise RuntimeError(f"no se pudo escribir {destino.name}")

    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if compuesto:
            frame = frame[:, x0:x0 + ancho_util]
        frame = cv2.resize(frame, (ANCHO_SALIDA, ALTO_SALIDA), interpolation=cv2.INTER_LANCZOS4)
        out.write(frame)
        n += 1

    cap.release()
    out.release()
    return ("recortado" if compuesto else "escalado"), n


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    origen_dir = Path(sys.argv[1])
    destino_dir = Path(sys.argv[2])

    if not origen_dir.is_dir():
        print(f"ERROR: no existe la carpeta {origen_dir}")
        return 2
    destino_dir.mkdir(parents=True, exist_ok=True)

    videos = sorted(p for p in origen_dir.iterdir() if p.suffix.lower() in EXTENSIONES)
    if not videos:
        print(f"ERROR: no hay videos en {origen_dir}")
        return 2

    fallos = []
    for i, origen in enumerate(videos, 1):
        destino = destino_dir / f"rgb-{origen.stem}.mp4"
        try:
            accion, frames = procesar(origen, destino)
            print(f"[{i:>3}/{len(videos)}] {origen.name:<40} {accion:<10} {frames:>4} frames")
        except Exception as exc:
            print(f"[{i:>3}/{len(videos)}] {origen.name:<40} ERROR: {exc}")
            fallos.append(origen.name)

    print(f"\nListo: {len(videos) - len(fallos)} de {len(videos)} en {destino_dir}")
    if fallos:
        print("Fallaron: " + ", ".join(fallos))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
