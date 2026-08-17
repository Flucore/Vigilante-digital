"""Router Edge/Hub — Vigilante Digital v2.0.

Define cómo se procesan y enrutan los frames y eventos según el modo de despliegue:

  edge    — Procesamiento 100% local (Sprint 1–3). Sin comunicación al hub.
  hub     — Frames comprimidos se envían al "cerebro" (servidor Curicó) para
             inferencia remota. El nodo local solo captura y transmite.
  hybrid  — Alertas críticas se procesan localmente (baja latencia < 1s SLA).
             Frames y eventos se envían al hub en paralelo para indexación.

Arquitectura de cola:
  - Thread-safe con asyncio Queue + backpressure
  - Si el hub no responde, los frames se descartan (no bloquea el loop principal)
  - Reintento automático con backoff exponencial para eventos críticos

FuenApa cerebro en Curicó: se conecta vía HTTP POST multipart/form-data.
Protocolo confirmado por cliente antes de implementar S4.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import cv2
import numpy as np

LOG = logging.getLogger(__name__)

# Intentar importar requests (debería estar siempre disponible)
try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False
    LOG.warning("[EdgeHubRouter] requests no disponible — modo hub/hybrid desactivado.")


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RouterConfig:
    """Configuración del router edge/hub.

    Atributos:
        mode:              "edge" | "hub" | "hybrid".
        hub_url:           URL base del servidor cerebro (ej: http://cerebro.fuenapa.cl:8080).
        hub_api_key_env:   Variable de entorno con la API key del hub.
        jpeg_quality:      Calidad de compresión JPEG para transmisión (1–100).
        max_queue_size:    Tamaño máximo de la cola de frames antes de descartar.
        send_timeout_sec:  Timeout para envío al hub.
        retry_critical:    Si True, reintenta envío de eventos críticos.
        node_id:           ID único de este nodo edge (para trazabilidad).
    """
    mode:            str   = "edge"
    hub_url:         str   = ""
    hub_api_key_env: str   = "HUB_API_KEY"
    jpeg_quality:    int   = 60
    max_queue_size:  int   = 30
    send_timeout_sec: float = 3.0
    retry_critical:  bool  = True
    node_id:         str   = "node_01"


# ──────────────────────────────────────────────────────────────────────────────
# EdgeHubRouter
# ──────────────────────────────────────────────────────────────────────────────

class EdgeHubRouter:
    """Enruta frames y eventos según el modo de despliegue configurado.

    Args:
        config: RouterConfig con el modo y parámetros de conexión.

    Ejemplo::

        cfg = RouterConfig(mode="hybrid", hub_url="http://cerebro.fuenapa.cl:8080")
        router = EdgeHubRouter(config=cfg)
        router.start()

        # En el loop principal:
        frame_out = router.route_frame(frame, camera_id="cam_01")
        router.route_event(event_dict, critical=True)

        router.stop()
    """

    def __init__(self, config: RouterConfig) -> None:
        self.config          = config
        self._running        = False
        self._send_thread:   Optional[threading.Thread] = None
        self._frame_queue:   queue.Queue = queue.Queue(maxsize=config.max_queue_size)
        self._event_queue:   queue.Queue = queue.Queue(maxsize=1000)
        self._stats          = _RouterStats()

        if config.mode not in ("edge", "hub", "hybrid"):
            raise ValueError(
                f"mode debe ser 'edge', 'hub' o 'hybrid'. Recibido: '{config.mode}'"
            )

        import os
        self._api_key = os.getenv(config.hub_api_key_env, "")
        if config.mode != "edge" and not self._api_key:
            LOG.warning(
                "[EdgeHubRouter] Variable '%s' no definida — "
                "envíos al hub sin autenticación.",
                config.hub_api_key_env,
            )

        LOG.info(
            "[EdgeHubRouter] mode=%s hub=%s node=%s",
            config.mode, config.hub_url or "N/A", config.node_id,
        )

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Inicia el hilo de envío al hub (solo en modo hub/hybrid)."""
        if self.config.mode == "edge":
            return
        self._running = True
        self._send_thread = threading.Thread(
            target=self._sender_loop, daemon=True, name="EdgeHubSender"
        )
        self._send_thread.start()
        LOG.info("[EdgeHubRouter] Hilo de envío iniciado.")

    def stop(self) -> None:
        """Detiene el hilo de envío y espera vaciado de cola."""
        self._running = False
        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=5.0)
        LOG.info("[EdgeHubRouter] Detenido. Stats: %s", self._stats)

    # ── Enrutamiento ──────────────────────────────────────────────────────────

    def route_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Enruta un frame según el modo configurado.

        Edge:   No hace nada con el frame (procesamiento local ya ocurrió).
        Hub:    Encola el frame para envío al hub.
        Hybrid: Encola el frame para envío; el procesamiento local ya ocurrió.

        Args:
            frame:     Frame BGR procesado.
            camera_id: ID de la cámara fuente.
            metadata:  Metadatos adicionales a enviar con el frame.

        Returns:
            Frame sin modificar.
        """
        if self.config.mode == "edge":
            return frame

        payload = {
            "camera_id": camera_id,
            "node_id":   self.config.node_id,
            "timestamp": time.time(),
            "metadata":  metadata or {},
        }

        try:
            self._frame_queue.put_nowait((frame.copy(), payload))
            self._stats.frames_queued += 1
        except queue.Full:
            self._stats.frames_dropped += 1
            LOG.debug("[EdgeHubRouter] Cola de frames llena — frame descartado.")

        return frame

    def route_event(
        self,
        event: Dict[str, Any],
        critical: bool = False,
    ) -> None:
        """Enruta un evento al hub.

        Edge:   No envía nada (log local a cargo del EventLogger).
        Hub/Hybrid: Encola el evento. Si es crítico y retry=True,
                    reintenta hasta 3 veces con backoff.

        Args:
            event:    Dict del evento (debe incluir "event_type", "camera_id", "timestamp").
            critical: Si True, el evento se reintenta en caso de fallo.
        """
        if self.config.mode == "edge":
            return

        enriched = {**event, "node_id": self.config.node_id, "critical": critical}
        try:
            self._event_queue.put_nowait(enriched)
            self._stats.events_queued += 1
        except queue.Full:
            LOG.warning("[EdgeHubRouter] Cola de eventos llena — evento descartado.")

    # ── Hilo de envío ─────────────────────────────────────────────────────────

    def _sender_loop(self) -> None:
        """Hilo background: procesa la cola y envía al hub."""
        while self._running or not self._event_queue.empty():
            # Procesar eventos primero (mayor prioridad)
            try:
                evt = self._event_queue.get_nowait()
                self._send_event(evt)
                self._event_queue.task_done()
            except queue.Empty:
                pass

            # Procesar frames
            try:
                frame, payload = self._frame_queue.get_nowait()
                self._send_frame(frame, payload)
                self._frame_queue.task_done()
            except queue.Empty:
                time.sleep(0.01)

    def _send_frame(self, frame: np.ndarray, payload: Dict[str, Any]) -> bool:
        """Comprime y envía un frame al hub."""
        if not _REQUESTS_AVAILABLE or not self.config.hub_url:
            return False

        try:
            _, buf = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality],
            )
            endpoint = f"{self.config.hub_url.rstrip('/')}/api/ingest/frame"
            resp = _requests.post(
                endpoint,
                files={"frame": ("frame.jpg", buf.tobytes(), "image/jpeg")},
                data={"payload": json.dumps(payload)},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self.config.send_timeout_sec,
            )
            if resp.status_code == 200:
                self._stats.frames_sent += 1
                return True
            LOG.warning("[EdgeHubRouter] Hub retornó HTTP %d para frame.", resp.status_code)
        except Exception as exc:
            LOG.debug("[EdgeHubRouter] Error enviando frame: %s", exc)
            self._stats.send_errors += 1
        return False

    def _send_event(
        self,
        event: Dict[str, Any],
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> bool:
        """Envía un evento al hub con reintentos si es crítico."""
        if not _REQUESTS_AVAILABLE or not self.config.hub_url:
            return False

        try:
            endpoint = f"{self.config.hub_url.rstrip('/')}/api/ingest/event"
            resp = _requests.post(
                endpoint,
                json=event,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type":  "application/json",
                },
                timeout=self.config.send_timeout_sec,
            )
            if resp.status_code == 200:
                self._stats.events_sent += 1
                return True
            LOG.warning("[EdgeHubRouter] Hub retornó HTTP %d para evento.", resp.status_code)
        except Exception as exc:
            LOG.debug("[EdgeHubRouter] Error enviando evento: %s", exc)
            self._stats.send_errors += 1

        # Reintento para eventos críticos
        if event.get("critical") and self.config.retry_critical and attempt < max_attempts:
            backoff = 2 ** attempt
            LOG.info("[EdgeHubRouter] Reintento %d/%d en %ds...", attempt + 1, max_attempts, backoff)
            time.sleep(backoff)
            return self._send_event(event, attempt + 1, max_attempts)

        return False

    # ── Estado / diagnóstico ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de envío al hub."""
        return {
            "frames_queued":  self._stats.frames_queued,
            "frames_sent":    self._stats.frames_sent,
            "frames_dropped": self._stats.frames_dropped,
            "events_queued":  self._stats.events_queued,
            "events_sent":    self._stats.events_sent,
            "send_errors":    self._stats.send_errors,
        }

    def __enter__(self) -> "EdgeHubRouter":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Estado interno
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _RouterStats:
    frames_queued:  int = 0
    frames_sent:    int = 0
    frames_dropped: int = 0
    events_queued:  int = 0
    events_sent:    int = 0
    send_errors:    int = 0
