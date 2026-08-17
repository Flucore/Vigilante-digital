"""Script mínimo para probar el almacenamiento de eventos canónicos (C2).

Uso:
  python scripts/test_event_storage.py --output test_outputs --no-firebase
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outputs.event_logger import EventLogger, enrich_canonical_event
from outputs.firebase_connector import FirebaseConnector

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("test_event_storage")


def main(output_dir: str, no_firebase: bool) -> int:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    event_log_path = out / "events_log.jsonl"
    logger = EventLogger(event_log_path)

    now = datetime.now(timezone.utc).isoformat()
    event = enrich_canonical_event(
        {
            "event_type": "fall",
            "start_time": now,
            "end_time": now,
            "duration_seconds": 2.5,
            "metadata": {"simulated": True, "fall_signal": "detector", "note": "test_event_storage"},
        },
        camera_id="CAM_TEST",
        zone="Lab",
        sector="Pruebas",
        alert_level=2,
        photo_path=None,
    )

    LOG.info("Guardando evento canónico localmente")
    logger.log_event(event)
    assert event.get("event_schema_version") == "2.0"
    assert event.get("timestamp")
    assert event.get("compliance", {}).get("retention_days")

    if no_firebase:
        LOG.info("--no-firebase especificado. No se intentará sincronizar con Firestore.")
        print(json.dumps({"status": "ok", "uploaded": 0, "event": event}, ensure_ascii=False, indent=2))
        return 0

    try:
        LOG.info("Inicializando FirebaseConnector para intentar sincronizar el evento")
        connector = FirebaseConnector(json_log_path=str(event_log_path), collection=None)
        uploaded = connector.sync_new_events()
        LOG.info("Sincronización completada. Eventos subidos: %s", uploaded)
        print(json.dumps({"status": "ok", "uploaded": uploaded}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        LOG.exception("Error al sincronizar con Firebase: %s", exc)
        print(json.dumps({"status": "error", "uploaded": 0, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba mínima de almacenamiento de eventos")
    parser.add_argument("--output", default="test_outputs", help="Directorio donde se escriben logs de eventos")
    parser.add_argument("--no-firebase", action="store_true", help="No intentar sincronizar con Firebase")
    args = parser.parse_args()
    sys.exit(main(output_dir=args.output, no_firebase=args.no_firebase))
