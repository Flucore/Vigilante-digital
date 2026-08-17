"""Cliente HTTP de bocina IP — capa outputs (sin importar inputs/).

Réplica operativa de la API usada por scripts/demo vía `inputs/ip_speaker.py`,
pero permitida en TriggerManager respetando la regla de capas.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

LOG = logging.getLogger(__name__)


def activate_http_speaker(
    host: str,
    *,
    event: Optional[Dict[str, Any]] = None,
    volume: Optional[int] = None,
    mp3_url: Optional[str] = None,
    timeout_sec: float = 3.0,
) -> bool:
    """Activa bocina por HTTP. Tolerante a fallas (nunca lanza al caller)."""
    if not host:
        LOG.warning("activate_http_speaker: host vacío")
        return False
    base = host.rstrip("/")
    timeout = float(timeout_sec)

    try:
        if volume is not None:
            _set_volume(base, int(volume), timeout)
        if mp3_url:
            return _play_url(base, str(mp3_url), timeout)
        return _post_json(f"{base}/alert", {"event": event or {}}, timeout)
    except Exception as exc:
        LOG.warning("activate_http_speaker falló (%s): %s", base, exc)
        return False


def _set_volume(base: str, level: int, timeout: float) -> bool:
    level = max(0, min(100, int(level)))
    try:
        r = requests.get(f"{base}/volume", params={"level": level}, timeout=timeout)
        if r.status_code // 100 == 2:
            return True
    except Exception:
        pass
    try:
        r = requests.post(f"{base}/volume", json={"level": level}, timeout=timeout)
        return r.status_code // 100 == 2
    except Exception:
        return False


def _play_url(base: str, mp3_url: str, timeout: float) -> bool:
    try:
        r = requests.get(f"{base}/play", params={"url": mp3_url}, timeout=timeout)
        if r.status_code // 100 == 2:
            return True
    except Exception:
        pass
    try:
        r = requests.post(f"{base}/play", json={"url": mp3_url}, timeout=timeout)
        if r.status_code // 100 == 2:
            return True
    except Exception:
        pass
    LOG.warning("play_url: dispositivo no aceptó endpoints conocidos (%s)", base)
    return False


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> bool:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code // 100 == 2:
            LOG.info("Speaker/webhook OK: %s", url)
            return True
        LOG.warning(
            "Speaker HTTP falló %s: status=%s body=%s",
            url, response.status_code, response.text[:200],
        )
        return False
    except Exception as exc:
        LOG.warning("Speaker HTTP error %s: %s", url, exc)
        return False
