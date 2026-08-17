"""Event-based logger para caídas (detección de inicio/fin).

Reemplaza el logging frame-a-frame con un sistema basado en eventos.
Reduce 5,330 registros a 1-2 por caída detectada.
"""
from __future__ import annotations

import json
import logging
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)


class EventLogger:
    """Registra eventos de caída (inicio/fin) en lugar de frames individuales.
    
    Máquina de estados:
    - NORMAL: sin detección de caída
    - FALLING: caída en progreso
    
    Cuando transiciona de FALLING → NORMAL, emite un evento completado.
    Esto reduce >99% de registros (5,330 → 1-2).
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """Inicializa el logger de eventos.
        
        Args:
            file_path: Ruta al archivo JSONL de eventos. Si es None, usa variable de entorno.
        """
        import os
        env_path = os.getenv("EVENT_LOG_PATH")
        self.path: Path = Path(file_path or env_path or "events_log.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        
        # Estado máquina: NORMAL o FALLING
        self.state: str = "NORMAL"
        self.fall_start_time: Optional[datetime] = None
        self.fall_start_frame: Optional[int] = None
        self.fall_photo_path: Optional[str] = None
        self.fall_metadata: Optional[Dict[str, Any]] = None

    def update(
        self, 
        is_falling: bool, 
        frame_idx: int, 
        photo_path: str = "", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Actualiza el estado y retorna un evento si hay cambio de estado.
        
        Args:
            is_falling: Si se detecta caída en este frame
            frame_idx: Índice del frame actual
            photo_path: Ruta a foto (capturada al inicio de caída)
            metadata: Datos adicionales (aspect_ratio, landmarks, etc.)
        
        Returns:
            Evento completado si transiciona FALLING → NORMAL, None en otro caso
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            completed_event = None

            if is_falling and self.state == "NORMAL":
                # TRANSICIÓN: NORMAL → FALLING (inicia caída)
                self.state = "FALLING"
                self.fall_start_time = now
                self.fall_start_frame = frame_idx
                self.fall_photo_path = photo_path
                self.fall_metadata = metadata or {}
                logger.info(f"[FALL_DETECTED] Caída iniciada en frame {frame_idx}")

            elif not is_falling and self.state == "FALLING":
                # TRANSICIÓN: FALLING → NORMAL (caída terminó)
                if self.fall_start_time is not None:
                    fall_end_time = now
                    duration = (fall_end_time - self.fall_start_time).total_seconds()
                    
                    completed_event = {
                        "event_type": "fall",
                        "start_time": self.fall_start_time.isoformat(),
                        "end_time": fall_end_time.isoformat(),
                        "duration_seconds": duration,
                        "start_frame": self.fall_start_frame,
                        "end_frame": frame_idx - 1,
                        "total_frames": frame_idx - self.fall_start_frame,
                        "photo_start": self.fall_photo_path,
                        "metadata": self.fall_metadata
                    }
                    
                    logger.info(f"[FALL_ENDED] Caída finalizada. Duración: {duration:.2f}s")
                
                self.state = "NORMAL"
                self.fall_start_time = None

            return completed_event

    def log_event(self, event: Dict[str, Any]) -> bool:
        """Guarda un evento completado como una línea JSONL.
        
        Args:
            event: Evento a guardar (retornado por update())
        
        Returns:
            True si tuvo éxito, False en caso de error
        """
        try:
            with self._lock:
                self._append_event(event)
            return True
        except Exception as exc:
            logger.exception(f"Error guardando evento: {exc}")
            return False

    def _read_history(self) -> List[Dict[str, Any]]:
        """Lee eventos desde JSONL y, por compatibilidad, desde arrays JSON legacy."""
        if not self.path.exists():
            return []
        
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                first = fh.read(1)
                fh.seek(0)
                if first == "[":
                    data = json.load(fh)
                    return data if isinstance(data, list) else []
                return list(_iter_jsonl(fh, self.path))
        except Exception:
            logger.exception(f"Error leyendo {self.path}")
            return []

    def _append_event(self, event: Dict[str, Any]) -> None:
        """Agrega un evento al final del archivo sin reescribir el historial."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        import os
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        """Escribe el historial completo como JSONL de forma atómica."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent))
        import os
        os.close(fd)
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                for event in history:
                    fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, str(self.path))
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def get_events(self) -> List[Dict[str, Any]]:
        """Retorna todos los eventos registrados."""
        return self._read_history()

    def clear(self) -> None:
        """Borra todos los eventos (para testing)."""
        with self._lock:
            self._write_history([])

    def finalize(self) -> Optional[Dict[str, Any]]:
        """Forzar cierre de un evento en progreso.

        Si el logger está en estado FALLING, construye y retorna el evento
        finalizado (como cuando se detecta la transición FALLING->NORMAL).
        Si no hay evento pendiente, retorna None.
        """
        with self._lock:
            if self.state != "FALLING":
                return None

            now = datetime.now(timezone.utc)
            if self.fall_start_time is None:
                # Estado inconsistente: resetear
                self.state = "NORMAL"
                return None

            duration = (now - self.fall_start_time).total_seconds()
            event = {
                "event_type": "fall",
                "start_time": self.fall_start_time.isoformat(),
                "end_time": now.isoformat(),
                "duration_seconds": duration,
                "start_frame": self.fall_start_frame,
                "end_frame": None,
                "total_frames": None,
                "photo_start": self.fall_photo_path,
                "metadata": self.fall_metadata,
                "finalized_forced": True,
            }

            # Reset state
            self.state = "NORMAL"
            self.fall_start_time = None
            self.fall_start_frame = None
            self.fall_photo_path = None
            self.fall_metadata = None

            logger.info(f"[FALL_FINALIZE] Evento finalizado forzadamente. Duración: {duration:.2f}s")
            return event


def _iter_jsonl(lines: Iterable[str], path: Path) -> Iterable[Dict[str, Any]]:
    """Itera objetos JSONL, ignorando líneas vacías y corruptas."""
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Línea JSONL inválida en %s:%d; se omite", path, line_no)
            continue
        if isinstance(item, dict):
            yield item
