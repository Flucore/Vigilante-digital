"""Lector de archivos de video MP4/AVI para Vigilante Digital.

Interfaz compatible con VideoStream (duck typing):
    open() → bool
    read() → Tuple[bool, Optional[np.ndarray]]
    close() → None
    context manager (__enter__ / __exit__)

Agrega barra de progreso en overlay para modo demo y batch.
En modo demo (draw_progress=True) se superpone información del frame
sobre la imagen: progreso, timestamp del video, módulo activo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# Colores HUD (BGR) — coherentes con hud_renderer.py
_C_BG       = (20, 20, 20)
_C_BAR      = (0, 165, 255)    # Naranja Vigilante
_C_TEXT     = (200, 200, 200)
_C_ACCENT   = (0, 165, 255)


class FileVideoReader:
    """Lector de archivos de video con barra de progreso en overlay.

    Args:
        source_path: Ruta al archivo MP4, AVI u otro formato soportado por OpenCV.
        loop: Si True, reinicia desde el principio al llegar al final.
        module_name: Nombre del módulo activo (mostrado en la barra de progreso).

    Ejemplo::

        reader = FileVideoReader("demo_video.mp4", module_name="fall_detection")
        with reader:
            while True:
                ok, frame = reader.read()
                if not ok:
                    break
                frame = reader.draw_progress(frame)
                cv2.imshow("Demo", frame)
    """

    def __init__(
        self,
        source_path: Union[str, Path],
        loop: bool = False,
        module_name: str = "",
    ) -> None:
        self.source_path = Path(source_path)
        self.loop = loop
        self.module_name = module_name

        self._cap: Optional[cv2.VideoCapture] = None
        self._opened: bool = False
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._fps: float = 25.0
        self._width: int = 0
        self._height: int = 0

    # ── Ciclo de vida ──────────────────────────────────────────────────────────

    def open(self) -> bool:
        """Abre el archivo de video. Retorna True si exitoso."""
        self.close()
        if not self.source_path.exists():
            LOG.error("[FileVideoReader] Archivo no encontrado: %s", self.source_path)
            return False

        self._cap = cv2.VideoCapture(str(self.source_path))
        self._opened = bool(self._cap and self._cap.isOpened())

        if self._opened:
            self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
            raw_fps = self._cap.get(cv2.CAP_PROP_FPS)
            self._fps = raw_fps if raw_fps > 0 else 25.0
            self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._current_frame = 0
            LOG.info(
                "[FileVideoReader] Abierto: '%s' | %dx%d | %.1f FPS | %d frames",
                self.source_path.name,
                self._width, self._height,
                self._fps, self._total_frames,
            )
        else:
            LOG.error("[FileVideoReader] No se pudo abrir: %s", self.source_path)

        return self._opened

    def close(self) -> None:
        """Libera el recurso de captura."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None
        self._opened = False

    # ── Lectura de frames ──────────────────────────────────────────────────────

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Lee el siguiente frame del archivo.

        Returns:
            (True, frame_bgr) mientras haya frames.
            (False, None) al terminar si loop=False.
            En modo loop nunca retorna (False, None) salvo error.
        """
        if self._cap is None or not self._opened:
            if not self.open():
                return False, None

        ok, frame = self._cap.read()

        if not ok or frame is None:
            if self.loop and self._total_frames > 0:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._current_frame = 0
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    return False, None
            else:
                LOG.info(
                    "[FileVideoReader] Fin del archivo '%s' (%d frames procesados).",
                    self.source_path.name, self._current_frame,
                )
                return False, None

        self._current_frame += 1
        return True, frame

    # ── Propiedades ───────────────────────────────────────────────────────────

    @property
    def total_frames(self) -> int:
        """Total de frames del archivo."""
        return self._total_frames

    @property
    def current_frame(self) -> int:
        """Frame actual (1-indexed)."""
        return self._current_frame

    @property
    def fps(self) -> float:
        """FPS del archivo de origen."""
        return self._fps

    @property
    def progress_ratio(self) -> float:
        """Progreso de 0.0 a 1.0."""
        if self._total_frames <= 0:
            return 0.0
        return min(1.0, self._current_frame / self._total_frames)

    @property
    def is_finished(self) -> bool:
        """True cuando el video llegó al final y loop=False."""
        return (not self.loop) and (self._current_frame >= self._total_frames > 0)

    def get_frame_timestamp_str(self) -> str:
        """Timestamp del frame actual expresado como HH:MM:SS.ff (tiempo relativo al video)."""
        seconds = self._current_frame / max(1.0, self._fps)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:05.2f}"

    def get_frame_iso_timestamp(self) -> str:
        """ISO 8601 UTC del momento real de procesamiento (no del video)."""
        return datetime.now(timezone.utc).isoformat()

    # ── Overlay de progreso ───────────────────────────────────────────────────

    def draw_progress(self, frame: np.ndarray) -> np.ndarray:
        """Dibuja barra de progreso y metadata sobre el frame (in-place).

        Args:
            frame: Frame BGR a anotar.

        Returns:
            El mismo frame con el overlay de progreso.
        """
        h, w = frame.shape[:2]
        bar_h = 30

        # Fondo semitransparente inferior
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - bar_h), (w, h), _C_BG, -1)
        cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

        # Barra de progreso (línea de 4px en la parte superior del bloque)
        ratio = self.progress_ratio
        fill_w = int(w * ratio)
        if fill_w > 0:
            cv2.rectangle(frame, (0, h - bar_h), (fill_w, h - bar_h + 4), _C_BAR, -1)

        # Texto izquierdo: frame / total | tiempo relativo | módulo
        module_txt = f"  [{self.module_name}]" if self.module_name else ""
        left_txt = (
            f"Frame {self._current_frame}/{self._total_frames}"
            f"  |  {self.get_frame_timestamp_str()}{module_txt}"
        )
        cv2.putText(
            frame, left_txt, (8, h - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.44, _C_TEXT, 1, cv2.LINE_AA,
        )

        # Texto derecho: porcentaje
        pct_txt = f"{ratio * 100:.1f}%"
        pct_w = cv2.getTextSize(pct_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)[0][0]
        cv2.putText(
            frame, pct_txt, (w - pct_w - 8, h - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.44, _C_ACCENT, 1, cv2.LINE_AA,
        )

        return frame

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "FileVideoReader":
        self.open()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"FileVideoReader('{self.source_path.name}', "
            f"frame={self._current_frame}/{self._total_frames}, "
            f"loop={self.loop})"
        )
