"""Gestor de triggers para eventos del Vigilante Digital.

El objetivo es desacoplar detección de acciones:
- Detectores producen eventos canónicos.
- TriggerManager decide qué acciones ejecutar: correo, WhatsApp/webhook, bocina.

Todos los triggers son opcionales y tolerantes a fallas.
Capa: solo importa outputs/ y libs externas — NUNCA inputs/.
"""
from __future__ import annotations

import atexit
import json
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests

from outputs.email_sender import EmailSender
from outputs.http_speaker import activate_http_speaker

LOG = logging.getLogger(__name__)


class TriggerManager:
    """Ejecuta acciones configurables al recibir eventos."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.enabled = bool(self.config.get("enabled", False))
        self._email_sender = EmailSender()
        max_workers = int(self.config.get("max_workers", 5))
        max_pending = int(self.config.get("max_pending", max_workers * 4))
        self._pending = threading.BoundedSemaphore(max(1, max_pending))
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="vigilante-trigger",
        )
        atexit.register(self.shutdown, wait=False)

    def handle_event(self, event: Dict[str, Any], pdf_path: Optional[str] = None) -> None:
        """Ejecuta triggers para un evento sin bloquear el loop principal."""
        if not self.enabled:
            return

        if not self._pending.acquire(blocking=False):
            LOG.warning("Cola de triggers llena; evento omitido: %s", event.get("event_type", "event"))
            return

        try:
            future = self._executor.submit(self._handle_event_safe, dict(event), pdf_path)
        except RuntimeError:
            self._pending.release()
            LOG.warning("Pool de triggers cerrado; evento omitido: %s", event.get("event_type", "event"))
            return
        future.add_done_callback(self._on_trigger_done)

    def _on_trigger_done(self, future: Future) -> None:
        self._pending.release()
        try:
            future.result()
        except Exception:
            LOG.exception("Error inesperado en worker de triggers")

    def shutdown(self, wait: bool = True) -> None:
        """Cierra el pool de triggers durante el apagado ordenado."""
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    def _handle_event_safe(self, event: Dict[str, Any], pdf_path: Optional[str]) -> None:
        try:
            event_type = event.get("event_type", "event")
            routes = self._routes_for(event_type)
            # Nivel 3: asegurar speaker si after_hours critical
            if int(event.get("alert_level", 1)) >= 3 and "speaker" not in routes:
                routes = list(routes) + ["speaker"]
            if not routes:
                LOG.debug("Sin triggers configurados para event_type=%s", event_type)
                return

            if "email" in routes:
                self._send_email(event, pdf_path)
            if "whatsapp" in routes:
                self._send_whatsapp(event)
            if "speaker" in routes:
                self._activate_speaker(event)
            if "webhook" in routes:
                self._send_webhook(event)
        except Exception:
            LOG.exception("Error inesperado ejecutando triggers")

    def _routes_for(self, event_type: str) -> Iterable[str]:
        routes_by_event = self.config.get("routes_by_event", {})
        routes = routes_by_event.get(event_type)
        if routes is None:
            routes = self.config.get("default_routes", [])
        return routes or []

    def _send_email(self, event: Dict[str, Any], pdf_path: Optional[str]) -> bool:
        cfg = self.config.get("email", {})
        recipient = cfg.get("recipient")
        if not recipient:
            LOG.warning("Trigger email sin recipient configurado")
            return False
        if not pdf_path or not Path(pdf_path).exists():
            LOG.warning("Trigger email requiere PDF existente; omitido")
            return False

        subject = cfg.get("subject", f"Alerta Vigilante Digital: {event.get('event_type')}")
        body = cfg.get("body") or _event_text(event)
        return self._email_sender.send_report(
            recipient_email=recipient,
            pdf_path=pdf_path,
            subject=subject,
            body=body,
        )

    def _send_whatsapp(self, event: Dict[str, Any]) -> bool:
        cfg = self.config.get("whatsapp", {})
        webhook_url = cfg.get("webhook_url")
        if not webhook_url:
            LOG.warning("Trigger WhatsApp sin webhook_url configurado")
            return False
        payload = {
            "channel": "whatsapp",
            "to": cfg.get("to"),
            "message": cfg.get("message_template", "Alerta Vigilante Digital") + "\n\n" + _event_text(event),
            "event": event,
        }
        return _post_json(webhook_url, payload, timeout=cfg.get("timeout_sec", 5.0))

    def _send_webhook(self, event: Dict[str, Any]) -> bool:
        cfg = self.config.get("webhook", {})
        url = cfg.get("url")
        if not url:
            LOG.warning("Trigger webhook sin URL configurada")
            return False
        return _post_json(url, {"event": event}, timeout=cfg.get("timeout_sec", 5.0))

    def _activate_speaker(self, event: Dict[str, Any]) -> bool:
        cfg = self.config.get("speaker", {})
        host = cfg.get("host")
        if not host:
            LOG.warning("Trigger speaker sin host configurado")
            return False
        return activate_http_speaker(
            str(host),
            event=event,
            volume=cfg.get("volume"),
            mp3_url=cfg.get("mp3_url"),
            timeout_sec=float(cfg.get("timeout_sec", 3.0)),
        )


def _event_text(event: Dict[str, Any]) -> str:
    return (
        f"Tipo: {event.get('event_type')}\n"
        f"Cámara: {event.get('camera_id', '-')}\n"
        f"Zona: {event.get('zone', '-')}\n"
        f"Nivel: {event.get('alert_level', '-')}\n"
        f"Hora: {event.get('timestamp') or event.get('start_time', '-')}\n"
        f"Detalle: {json.dumps(event.get('metadata', {}), ensure_ascii=False)}"
    )


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> bool:
    try:
        response = requests.post(url, json=payload, timeout=float(timeout))
        if response.status_code // 100 == 2:
            LOG.info("Webhook OK: %s", url)
            return True
        LOG.warning("Webhook falló %s: status=%s body=%s", url, response.status_code, response.text[:200])
        return False
    except Exception as exc:
        LOG.warning("Webhook error %s: %s", url, exc)
        return False
