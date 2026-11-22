"""Arma el video de demostración del correo: 5 caídas en ~30 s.

Une clips del conjunto de validación (data/goldset) en un solo archivo que
se usa como "cámara IP simulada" en demo_camara_ip.py. Entre caída y caída
intercala un tramo corto de actividad diaria: al ver a una persona de pie,
el detector cierra el episodio de caída y despacha el correo.

Criterio de selección (eval/verificacion/detalle.csv):
- Caídas: las 5 más largas que el criterio bbox detecta (VP); traen
  caminata antes de caer y ~1,5 s en el suelo después de la alarma.
- Separadores: inicio de clips ADL que ambos criterios dejan sin alarma (VN).

El resultado NO es parte del experimento: se guarda fuera de data/goldset
y es un montaje para la presentación, no un registro real.

Uso:
    python scripts/armar_video_demo.py
    python scripts/armar_video_demo.py --salida data/demo/otro.mp4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
GOLDSET = ROOT / "data" / "goldset"

# Orden del montaje: (clip, segundos a tomar desde el inicio; None = completo)
SEGMENTS: list[tuple[str, float | None]] = [
    ("rgb-fall-09-cam0.mp4", None),   # caída 1 (camina ~4 s antes de caer)
    ("rgb-adl-02-cam0.mp4", 1.5),
    ("rgb-fall-05-cam0.mp4", None),   # caída 2
    ("rgb-adl-05-cam0.mp4", 1.5),
    ("rgb-fall-07-cam0.mp4", None),   # caída 3
    ("rgb-adl-07-cam0.mp4", 1.5),
    ("rgb-fall-01-cam0.mp4", None),   # caída 4
    ("rgb-adl-09-cam0.mp4", 1.5),
    ("rgb-fall-11-cam0.mp4", None),   # caída 5
    ("rgb-adl-03-cam0.mp4", 1.5),     # cierre: de pie, termina el último episodio
]

DEFAULT_OUTPUT = ROOT / "data" / "demo" / "caidas_demo_30s.mp4"


def build(output: Path) -> tuple[int, float]:
    """Escribe el montaje y devuelve (cuadros, segundos)."""
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    fps = 30.0
    total = 0
    try:
        for name, seconds in SEGMENTS:
            path = GOLDSET / name
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                raise FileNotFoundError(f"No se pudo abrir {path}")
            clip_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            if writer is None:
                fps = clip_fps
                size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
            limit = int(round(seconds * clip_fps)) if seconds else None
            taken = 0
            while limit is None or taken < limit:
                ok, frame = cap.read()
                if not ok:
                    break
                writer.write(frame)
                taken += 1
            cap.release()
            total += taken
            print(f"  {name:<24} {taken:>4} cuadros")
    finally:
        if writer is not None:
            writer.release()
    return total, total / fps


def main() -> None:
    p = argparse.ArgumentParser(description="Arma el video de demo con 5 caídas.")
    p.add_argument("--salida", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    try:
        frames, seconds = build(args.salida)
    except FileNotFoundError as exc:
        sys.exit(f"[ERROR] {exc}")
    print(f"Listo: {args.salida} — {frames} cuadros, {seconds:.1f} s")


if __name__ == "__main__":
    main()
