"""Completa inicio_caida_s en labels.csv usando las etiquetas de UR Fall.

Lee urfall-cam0-falls.csv (una fila por frame: secuencia, frame, etiqueta, ...)
y toma como inicio de la caída el primer frame con etiqueta 0 (pose transitoria).
Si una secuencia no tiene etiqueta 0, usa el primer frame con etiqueta 1.

Uso:
    python anotar_desde_urfall.py urfall-cam0-falls.csv data/labels.csv data/goldset
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import cv2

RE_SECUENCIA = re.compile(r"(fall-\d+)", re.IGNORECASE)
FPS_POR_DEFECTO = 30.0


def leer_etiquetas_urfall(path: Path) -> dict[str, dict[int, int]]:
    """Devuelve {secuencia: {frame: etiqueta}}."""
    por_secuencia: dict[str, dict[int, int]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for fila in csv.reader(f):
            if len(fila) < 3:
                continue
            seq = fila[0].strip().strip('"').lower()
            if not RE_SECUENCIA.fullmatch(seq):
                continue  # cabecera u otra cosa
            try:
                frame = int(float(fila[1]))
                etiqueta = int(float(fila[2]))
            except ValueError:
                continue
            por_secuencia.setdefault(seq, {})[frame] = etiqueta
    return por_secuencia


def inicio_de_caida(frames: dict[int, int]) -> tuple[int, str] | None:
    """Primer frame con etiqueta 0; si no hay, el primero con etiqueta 1."""
    ceros = sorted(f for f, e in frames.items() if e == 0)
    if ceros:
        return ceros[0], "transicion"
    unos = sorted(f for f, e in frames.items() if e == 1)
    if unos:
        return unos[0], "tendido"
    return None


def fps_de(path: Path) -> float:
    if not path.exists():
        return FPS_POR_DEFECTO
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return FPS_POR_DEFECTO
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps and fps > 0 else FPS_POR_DEFECTO


def n_frames_de(path: Path) -> int:
    if not path.exists():
        return 0
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return 0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2

    urfall_csv = Path(sys.argv[1])
    labels_csv = Path(sys.argv[2])
    clips_dir = Path(sys.argv[3])

    for p in (urfall_csv, labels_csv):
        if not p.is_file():
            print(f"ERROR: no existe {p}")
            return 2

    etiquetas = leer_etiquetas_urfall(urfall_csv)
    if not etiquetas:
        print(f"ERROR: no se reconoció ninguna secuencia en {urfall_csv}.")
        print("Revisa que sea urfall-cam0-falls.csv y que la primera columna "
              "tenga nombres como 'fall-01'.")
        return 2
    print(f"Leídas {len(etiquetas)} secuencias de {urfall_csv.name}\n")

    with labels_csv.open("r", encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        columnas = lector.fieldnames or []
        filas = list(lector)

    completadas = 0
    sin_datos: list[str] = []
    avisos: list[str] = []

    for fila in filas:
        if fila.get("etiqueta") != "caida":
            continue
        m = RE_SECUENCIA.search(fila["archivo"])
        if not m:
            sin_datos.append(f"{fila['archivo']} (no pude deducir la secuencia)")
            continue
        seq = m.group(1).lower()
        frames = etiquetas.get(seq)
        if not frames:
            sin_datos.append(f"{fila['archivo']} (sin filas para '{seq}')")
            continue
        inicio = inicio_de_caida(frames)
        if inicio is None:
            sin_datos.append(f"{fila['archivo']} (sin etiquetas 0 ni 1)")
            continue

        frame, origen = inicio
        video = clips_dir / fila["archivo"]
        fps = fps_de(video)
        segundos = max(0.0, (frame - 1) / fps)
        fila["inicio_caida_s"] = f"{segundos:.2f}"
        completadas += 1

        n_video = n_frames_de(video)
        n_csv = max(frames)
        if n_video and abs(n_video - n_csv) > 2:
            avisos.append(
                f"{fila['archivo']}: el video tiene {n_video} frames y el CSV "
                f"llega al {n_csv}. Revisa que correspondan."
            )
        marca = "" if origen == "transicion" else "  (sin frames de transición: uso el primero tendido)"
        print(f"  {fila['archivo']:<32} frame {frame:>4} -> {segundos:5.2f} s{marca}")

    with labels_csv.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)

    print(f"\nCompletadas {completadas} de "
          f"{sum(1 for f in filas if f.get('etiqueta') == 'caida')} caídas "
          f"en {labels_csv}")

    if avisos:
        print("\nAvisos:")
        for a in avisos:
            print(f"  {a}")
    if sin_datos:
        print("\nQuedaron sin completar (anótalas a mano):")
        for s in sin_datos:
            print(f"  {s}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
