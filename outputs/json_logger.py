from __future__ import annotations
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

class JSONLogger:
    """Registra eventos en un archivo JSONL histórico.

    Cada entrada es un dict con al menos:
      - timestamp (ISO 8601 UTC)
      - photo_path (ruta al archivo de la foto)
      - event_type (p. ej. "fall")
      - metadata (opcional; dict libre)

    Diseño:
      - No importa módulos de `core/` ni `inputs/`.
      - Agrega eventos con append-only JSONL para evitar reescrituras O(N).
      - Lee archivos JSON array legacy para compatibilidad.
      - Protege acceso concurrente dentro del mismo proceso con threading.Lock.
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Inicializa el logger.

        Args:
            file_path: ruta al archivo JSONL. Si es None, intenta leer de la env VAR `JSON_LOG_PATH`
                       y si no existe, usa `./events_history.jsonl`.
        """
        env_path = os.getenv("JSON_LOG_PATH")
        self.path: Path = Path(file_path or env_path or "events_history.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log_event(
        self,
        timestamp: Optional[Union[str, datetime]] = None,
        photo_path: str = "",
        event_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Añade una entrada al historial JSONL.

        Args:
            timestamp: ISO string o datetime. Si None, se usa UTC ahora.
            photo_path: ruta a la foto asociada al evento.
            event_type: tipo de evento (ej. "fall", "false_positive").
            metadata: datos extra arbitrarios.

        Returns:
            True si la operación fue exitosa, False en caso de error (se registrará internamente).
        """
        if metadata is None:
            metadata = {}

        # Normalizar timestamp
        ts_iso = self._normalize_timestamp(timestamp)

        entry: Dict[str, Any] = {
            "timestamp": ts_iso,
            "photo_path": photo_path,
            "event_type": event_type,
            "metadata": metadata,
        }

        try:
            with self._lock:
                self._append_entry(entry)
            return True
        except Exception:
            # No levantar para no romper el orquestador; caller puede optar por reintentar
            return False

    def _normalize_timestamp(self, timestamp: Optional[Union[str, datetime]]) -> str:
        """Convierte timestamp a ISO 8601 UTC string."""
        if timestamp is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                ts = timestamp.replace(tzinfo=timezone.utc)
            else:
                ts = timestamp.astimezone(timezone.utc)
            return ts.isoformat()
        # Suponemos string ya en un formato legible; devolver tal cual
        return str(timestamp)

    def _read_history(self) -> List[Dict[str, Any]]:
        """Lee JSONL y, por compatibilidad, arrays JSON legacy."""
        if not self.path.exists():
            return []

        try:
            with self.path.open("r", encoding="utf-8") as fh:
                first = fh.read(1)
                fh.seek(0)
                if first == "[":
                    data = json.load(fh)
                    if isinstance(data, list):
                        return data
                    self._backup_corrupt_file("not-a-list")
                    return []
                return list(_iter_jsonl(fh, self.path))
        except json.JSONDecodeError:
            self._backup_corrupt_file("json-decode-error")
            return []
        except Exception:
            # En cualquier otro fallo devolvemos vacio (no propagar)
            return []

    def _append_entry(self, entry: Dict[str, Any]) -> None:
        """Agrega una línea JSONL sin leer ni reescribir el historial."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        """Escribe un historial completo como JSONL usando temp y os.replace."""
        dirpath = self.path.parent
        dirpath.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix=self.path.name + ".", suffix=".tmp")
        os.close(fd)
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                for entry in history:
                    fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self.path)  # atomic replace
        finally:
            # limpiar si quedó algo
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _backup_corrupt_file(self, reason: str) -> None:
        """Mueve el archivo corrupto a un backup con timestamp para análisis."""
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_name = f"{self.path.name}.corrupt.{reason}.{ts}"
            backup_path = self.path.with_name(backup_name)
            os.replace(self.path, backup_path)
        except Exception:
            # No propagar; si no se puede respaldar, el método superior seguirá con lista vacía
            pass


def _iter_jsonl(lines: Iterable[str], path: Path) -> Iterable[Dict[str, Any]]:
    """Itera objetos JSONL, ignorando líneas vacías y corruptas."""
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            # Un registro corrupto no debe tumbar el proceso 24/7.
            continue
        if isinstance(item, dict):
            yield item