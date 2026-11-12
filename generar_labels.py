"""Genera el esqueleto de data/labels.csv a partir de los clips.

Deduce la etiqueta del nombre del archivo (fall -> caida, adl -> no_caida)
y deja inicio_caida_s vacío para que lo completes a mano en los positivos.

Uso:
    python generar_labels.py data/goldset data/labels.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2

EXTENSIONES = {".mp4", ".avi", ".mov", ".mkv"}
COLUMNAS = ["archivo", "etiqueta", "inicio_caida_s", "escenario", "locacion"]


def etiqueta_de(nombre: str) -> str | None:
    n = nombre.lower()
    if "fall" in n:
        return "caida"
    if "adl" in n:
        return "no_caida"
    return None


def duracion_s(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return 0.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return frames / fps if fps else 0.0


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    clips_dir = Path(sys.argv[1])
    salida = Path(sys.argv[2])

    if not clips_dir.is_dir():
        print(f"ERROR: no existe la carpeta {clips_dir}")
        return 2

    videos = sorted(p for p in clips_dir.iterdir() if p.suffix.lower() in EXTENSIONES)
    if not videos:
        print(f"ERROR: no hay videos en {clips_dir}")
        return 2

    filas = []
    sin_etiqueta = []
    for v in videos:
        et = etiqueta_de(v.name)
        if et is None:
            sin_etiqueta.append(v.name)
            et = ""
        filas.append({
            "archivo": v.name,
            "etiqueta": et,
            "inicio_caida_s": "",
            "escenario": "caida" if et == "caida" else "actividad diaria",
            "locacion": "oficina",
        })

    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)

    caidas = [f for f in filas if f["etiqueta"] == "caida"]
    print(f"Escrito {salida} con {len(filas)} filas "
          f"({len(caidas)} caidas, {len(filas) - len(caidas)} no_caida)\n")

    if sin_etiqueta:
        print("ATENCIÓN: no pude deducir la etiqueta de estos archivos. "
              "Complétala a mano:")
        for n in sin_etiqueta:
            print(f"  {n}")
        print()

    print("Duración de los clips a anotar (inicio_caida_s):")
    for f in caidas:
        d = duracion_s(clips_dir / f["archivo"])
        print(f"  {f['archivo']:<32} {d:5.1f} s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
