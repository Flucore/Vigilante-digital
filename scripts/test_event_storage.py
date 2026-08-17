"""Script mínimo para probar el almacenamiento de eventos.

Este script crea un `EventLogger`, genera un evento de ejemplo y:
 - lo guarda en el historial local
 - lo escribe en el log de eventos
 - intenta sincronizar con Firebase si no se pasa --no-firebase

Uso:
  python scripts/test_event_storage.py --output test_outputs --no-firebase
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outputs.event_logger import EventLogger
from outputs.firebase_connector import FirebaseConnector

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("test_event_storage")


def main(output_dir: str, no_firebase: bool):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    event_log_path = out / "events_log.jsonl"

    logger = EventLogger(event_log_path)

    # Evento de prueba: simulated fall
    event = {
        "event_type": "fall",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 2.5,
        "frames": [100, 101, 102],
        "metadata": {"simulated": True, "note": "test_event_storage"}
    }

    LOG.info("Guardando evento de prueba localmente en EventLogger")
    logger.log_event(event)

    if no_firebase:
        LOG.info("--no-firebase especificado. No se intentará sincronizar con Firestore.")
        print(json.dumps({"status": "ok", "uploaded": 0}, ensure_ascii=False, indent=2))
        return 0

    try:
        LOG.info("Inicializando FirebaseConnector para intentar sincronizar el evento")
        connector = FirebaseConnector(json_log_path=str(event_log_path), collection=None)
        uploaded = connector.sync_new_events()
        LOG.info(f"Sincronización completada. Eventos subidos: {uploaded}")
        print(json.dumps({"status": "ok", "uploaded": uploaded}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        LOG.exception("Error al sincronizar con Firebase: %s", exc)
        print(json.dumps({"status": "error", "uploaded": 0, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Prueba mínima de almacenamiento de eventos")
    parser.add_argument('--output', default='test_outputs', help='Directorio donde se escriben logs de eventos')
    parser.add_argument('--no-firebase', action='store_true', help='No intentar sincronizar con Firebase')
    args = parser.parse_args()

    sys.exit(main(output_dir=args.output, no_firebase=args.no_firebase))
