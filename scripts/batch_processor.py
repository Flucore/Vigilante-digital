"""Pipeline batch para procesamiento de video histórico — Vigilante Digital v2.0.

Procesa archivos MP4/AVI a máxima velocidad GPU (sin UI, sin waitKey)
y vuelca los metadatos de detección en ForensicDB (PostgreSQL o JSONL fallback).

Uso:
    python scripts/batch_processor.py --source video.mp4
    python scripts/batch_processor.py --source grabaciones/ --config client_config.json
    python scripts/batch_processor.py --source video.mp4 --output-db postgresql://...

Al terminar imprime un resumen con:
    - Frames procesados / total
    - FPS de procesamiento efectivo
    - Conteo de detecciones por clase
    - Tiempo total y ETA (mostrado en progreso)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Asegurar root en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config_loader import ConfigLoader
from core.detector_factory import get_detector, detector_info
from inputs.file_reader import FileVideoReader
from outputs.metadata_indexer import MetadataIndexer
from outputs.forensic_db import ForensicDB, SearchFilters

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
LOG = logging.getLogger("vigilante.batch")

# ──────────────────────────────────────────────────────────────────────────────
# Barra de progreso de consola (sin dependencias externas)
# ──────────────────────────────────────────────────────────────────────────────

def _progress_bar(current: int, total: int, fps: float, eta_sec: float, prefix: str = "") -> None:
    """Imprime barra de progreso en la misma línea de consola."""
    if total <= 0:
        pct = 0.0
        bar = "[" + "-" * 30 + "]"
    else:
        pct = min(100.0, current / total * 100)
        filled = int(30 * current / total)
        bar = "[" + "#" * filled + "-" * (30 - filled) + "]"

    eta_str = f"{int(eta_sec // 60):02d}:{int(eta_sec % 60):02d}" if eta_sec < 3600 else ">1h"
    line = f"\r{prefix}{bar} {pct:5.1f}% | frame {current}/{total} | {fps:.1f} FPS | ETA {eta_str}   "
    sys.stdout.write(line)
    sys.stdout.flush()


# ──────────────────────────────────────────────────────────────────────────────
# Procesamiento de un archivo
# ──────────────────────────────────────────────────────────────────────────────

def process_file(
    source: Path,
    loader: ConfigLoader,
    db: ForensicDB,
    cam_id: str = "BATCH_CAM",
) -> Dict[str, Any]:
    """Procesa un archivo de video y vuelca detecciones en ForensicDB.

    Args:
        source: Path al archivo MP4/AVI.
        loader: Configuración del cliente.
        db: Instancia de ForensicDB (postgres o jsonl).
        cam_id: ID de cámara a asociar con las detecciones.

    Returns:
        Dict con estadísticas del procesamiento.
    """
    det_cfg = loader.get_section("detection", {})
    forensic_cfg = loader.get_section("forensic_audit", {})
    index_every_n = int(forensic_cfg.get("index_every_n_frames", 5))

    # Detector
    detector = None
    engine_info: Dict[str, str] = {"engine": "none", "device": "CPU"}
    try:
        detector = get_detector(
            use_gpu=det_cfg.get("use_gpu", True),
            min_fall_frames=det_cfg.get("min_fall_frames", 8),
            fall_angle_deg=det_cfg.get("fall_angle_threshold_deg", 55.0),
        )
        engine_info = detector_info(detector)
        LOG.info("[batch] Motor: %s / %s", engine_info.get("engine"), engine_info.get("device"))
    except Exception as exc:
        LOG.warning("[batch] Detector no disponible: %s. Procesando sin inferencia.", exc)

    # MetadataIndexer → ForensicDB pipeline
    idx_path = ROOT / forensic_cfg.get("output_jsonl", "outputs/metadata_index.jsonl")
    indexer = MetadataIndexer(idx_path, index_every_n_frames=index_every_n)

    reader = FileVideoReader(source, loop=False, module_name="batch")
    if not reader.open():
        LOG.error("[batch] No se pudo abrir: %s", source)
        return {"file": str(source), "error": "no_open"}

    stats: Dict[str, Any] = {
        "file": str(source),
        "total_frames": reader.total_frames,
        "processed_frames": 0,
        "detections_total": 0,
        "detections_by_class": {},
        "processing_fps": 0.0,
        "duration_sec": 0.0,
        "engine": engine_info.get("engine", "none"),
    }

    t_start = time.time()
    frame_idx = 0
    det_count = 0

    print(f"\n  Archivo : {source.name}")
    print(f"  Frames  : {reader.total_frames} @ {reader.fps:.1f} FPS | Motor: {engine_info.get('engine')}")
    print()

    try:
        while True:
            ok, frame = reader.read()
            if not ok or frame is None:
                break

            frame_idx += 1
            detections_this_frame: List[Dict] = []

            if detector is not None and frame_idx % index_every_n == 0:
                try:
                    proc_frame, results = detector.find_pose(frame, draw=False)
                    _, bbox = detector.find_position(proc_frame, results, draw=False)
                    if bbox:
                        det = {
                            "object_class": "person",
                            "confidence": float(bbox.get("confidence", 0.8)),
                            "bbox": {k: bbox.get(k, 0) for k in ("xmin", "ymin", "xmax", "ymax")},
                            "track_id": bbox.get("track_id"),
                            "metadata": {"is_falling": bbox.get("is_falling", False)},
                        }
                        detections_this_frame.append(det)
                        det_count += 1
                        cls = det["object_class"]
                        stats["detections_by_class"][cls] = stats["detections_by_class"].get(cls, 0) + 1
                except Exception:
                    pass

            if detections_this_frame:
                ts = datetime.now(timezone.utc).isoformat()
                indexer.index_frame(
                    frame_idx=frame_idx,
                    timestamp=ts,
                    camera_id=cam_id,
                    detections=detections_this_frame,
                    frame=frame,
                )
                # Enviar a ForensicDB si está en modo postgres
                for det in detections_this_frame:
                    det["camera_id"] = cam_id
                    det["timestamp"] = ts
                    det["frame_idx"] = frame_idx
                    db.insert_detection(det)

            # Progreso en consola
            elapsed = time.time() - t_start
            current_fps = frame_idx / max(elapsed, 0.001)
            if reader.total_frames > 0:
                remaining = reader.total_frames - frame_idx
                eta = remaining / max(current_fps, 0.001)
            else:
                eta = 0.0

            if frame_idx % 50 == 0 or frame_idx == reader.total_frames:
                _progress_bar(frame_idx, reader.total_frames, current_fps, eta, prefix="  ")

    except KeyboardInterrupt:
        print("\n  [!] Interrumpido por el usuario.")
    finally:
        reader.close()
        indexer.close()
        db.flush()
        if detector is not None:
            try:
                detector.close()
            except Exception:
                pass

    elapsed_total = time.time() - t_start
    stats["processed_frames"] = frame_idx
    stats["detections_total"] = det_count
    stats["processing_fps"] = round(frame_idx / max(elapsed_total, 0.001), 1)
    stats["duration_sec"] = round(elapsed_total, 2)

    print(f"\n\n  Completado en {elapsed_total:.1f}s @ {stats['processing_fps']} FPS de procesamiento")
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Reporte de resumen
# ──────────────────────────────────────────────────────────────────────────────

def print_summary(all_stats: List[Dict[str, Any]], db: ForensicDB) -> None:
    """Imprime resumen en consola y escribe JSON."""
    print("\n" + "=" * 60)
    print("  RESUMEN DEL BATCH")
    print("=" * 60)

    total_frames = sum(s.get("processed_frames", 0) for s in all_stats)
    total_dets   = sum(s.get("detections_total", 0) for s in all_stats)
    total_time   = sum(s.get("duration_sec", 0) for s in all_stats)
    avg_fps      = round(total_frames / max(total_time, 0.001), 1)

    print(f"  Archivos procesados : {len(all_stats)}")
    print(f"  Frames totales      : {total_frames}")
    print(f"  Detecciones totales : {total_dets}")
    print(f"  Tiempo total        : {total_time:.1f}s")
    print(f"  FPS promedio        : {avg_fps}")

    # Conteo consolidado por clase
    class_counts: Dict[str, int] = {}
    for s in all_stats:
        for cls, cnt in s.get("detections_by_class", {}).items():
            class_counts[cls] = class_counts.get(cls, 0) + cnt
    if class_counts:
        print("\n  Detecciones por clase:")
        for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
            print(f"    {cls:<20} {cnt}")

    # Stats de la BD
    db_stats = db.get_summary_stats()
    print(f"\n  BD — total registros: {db_stats.get('total_detections', '?')}")
    print(f"  BD — modo           : {db_stats.get('mode', '?')}")

    # Escribir JSON de resumen
    summary = {
        "batch_timestamp": datetime.now(timezone.utc).isoformat(),
        "files": all_stats,
        "totals": {
            "files": len(all_stats),
            "frames": total_frames,
            "detections": total_dets,
            "duration_sec": total_time,
            "avg_fps": avg_fps,
        },
        "db_stats": db_stats,
    }
    out_path = ROOT / "outputs" / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Resumen guardado en: {out_path.relative_to(ROOT)}")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="batch_processor.py",
        description="Vigilante Digital — Procesador Batch de Video Histórico",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/batch_processor.py --source grabacion.mp4
  python scripts/batch_processor.py --source carpeta_videos/
  python scripts/batch_processor.py --source video.mp4 --output-db postgresql://user:pass@host/vigilante
        """,
    )
    p.add_argument("--source",      required=True, help="Archivo MP4 o directorio con videos")
    p.add_argument("--config",      default="client_config.json", help="Config del cliente")
    p.add_argument("--output-db",   default=None, help="URL PostgreSQL (sobrescribe AUDIT_DB_URL)")
    p.add_argument("--cam-id",      default="BATCH_CAM", help="ID de cámara a asignar a las detecciones")
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Configuración
    try:
        loader = ConfigLoader(ROOT / args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    forensic_cfg = loader.get_section("forensic_audit", {})
    db_url = args.output_db or os.getenv("AUDIT_DB_URL", "")
    jsonl_path = ROOT / forensic_cfg.get("output_jsonl", "outputs/metadata_index.jsonl")

    db = ForensicDB(db_url=db_url, jsonl_path=str(jsonl_path))

    # Recolectar archivos a procesar
    source = Path(args.source)
    if source.is_dir():
        files = sorted(source.glob("*.mp4")) + sorted(source.glob("*.avi"))
        if not files:
            print(f"[ERROR] No se encontraron archivos MP4/AVI en: {source}", file=sys.stderr)
            sys.exit(1)
    elif source.is_file():
        files = [source]
    else:
        print(f"[ERROR] Fuente no encontrada: {source}", file=sys.stderr)
        sys.exit(1)

    print(f"\nVigilante Digital — Procesador Batch")
    print(f"Archivos a procesar: {len(files)}")
    print(f"Configuración      : {args.config}")
    print(f"Base de datos      : {'PostgreSQL' if db_url else 'JSONL fallback'}\n")

    all_stats: List[Dict] = []
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Procesando: {f.name}")
        stats = process_file(f, loader, db, cam_id=args.cam_id)
        all_stats.append(stats)

    print_summary(all_stats, db)
    db.close()


if __name__ == "__main__":
    main()
