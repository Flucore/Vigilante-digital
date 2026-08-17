"""Conector ONVIF para cámaras IP — Vigilante Digital v2.0.

Soporta descubrimiento WS-Discovery, obtención de URI RTSP y control PTZ.
Cuando onvif-zeep no está instalado, degrada a conexión RTSP directa.

Estándares:
  ONVIF Profile S — Video Streaming
  ONVIF Profile T — Advanced Video Streaming (PTZ)
  WS-Discovery     — Descubrimiento automático en subred

Seguridad: la contraseña NUNCA se pasa como literal; siempre desde variable de entorno.

Uso::
    connector = ONVIFConnector(host="192.168.1.100", port=80,
                               user="admin", password_env="CAM_01_PASSWORD")
    uri = connector.get_stream_uri()
    info = connector.get_device_info()
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LOG = logging.getLogger(__name__)

# Intentar importar onvif-zeep
try:
    from onvif import ONVIFCamera as _ONVIFCamera
    from onvif.exceptions import ONVIFError
    import zeep.exceptions as _zeep_exc
    _ONVIF_AVAILABLE = True
except ImportError:
    _ONVIF_AVAILABLE = False
    LOG.warning(
        "[ONVIFConnector] onvif-zeep no disponible. "
        "Instalar: pip install onvif-zeep\n"
        "Fallback: conexión RTSP directa por URL."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ONVIFCameraInfo:
    """Información de una cámara descubierta por ONVIF.

    Atributos:
        host:            IP o hostname de la cámara.
        port:            Puerto del servicio ONVIF (default 80).
        stream_uri:      URL RTSP del stream principal.
        profile_token:   Token de perfil de video seleccionado.
        manufacturer:    Fabricante (Hikvision, Dahua, Axis, …).
        model:           Modelo del equipo.
        firmware:        Versión de firmware.
        serial_number:   Número de serie.
        supports_ptz:    True si la cámara soporta PTZ.
    """
    host:           str
    port:           int            = 80
    stream_uri:     str            = ""
    profile_token:  str            = ""
    manufacturer:   str            = "unknown"
    model:          str            = "unknown"
    firmware:       str            = "unknown"
    serial_number:  str            = "unknown"
    supports_ptz:   bool           = False
    raw_profiles:   List[Any]      = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# ONVIFConnector
# ──────────────────────────────────────────────────────────────────────────────

class ONVIFConnector:
    """Conector ONVIF para una cámara IP.

    Args:
        host:         IP o hostname de la cámara.
        port:         Puerto del servicio ONVIF (default 80).
        user:         Nombre de usuario ONVIF.
        password_env: Nombre de la variable de entorno con la contraseña.
                      NUNCA pasar la contraseña literal.
        rtsp_fallback_url: URL RTSP a usar si ONVIF no está disponible.
                           Si se provee, también se usa cuando ONVIF falla.

    Ejemplo::

        c = ONVIFConnector("192.168.1.64", 80, "admin", "CAM_PATIO_PASS",
                           rtsp_fallback_url="rtsp://192.168.1.64:554/stream1")
        uri = c.get_stream_uri()
    """

    def __init__(
        self,
        host: str,
        port: int = 80,
        user: str = "admin",
        password_env: str = "ONVIF_PASSWORD",
        rtsp_fallback_url: str = "",
    ) -> None:
        self.host               = host
        self.port               = port
        self.user               = user
        self._password_env      = password_env
        self.rtsp_fallback_url  = rtsp_fallback_url
        self._cam: Optional[Any] = None
        self._connected         = False

        LOG.info(
            "[ONVIFConnector] host=%s port=%d user=%s onvif_lib=%s",
            host, port, user, _ONVIF_AVAILABLE,
        )

    # ── Conexión ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Establece conexión con la cámara via ONVIF.

        Returns:
            True si la conexión fue exitosa.
        """
        if not _ONVIF_AVAILABLE:
            LOG.info("[ONVIFConnector] Modo RTSP directo (onvif-zeep no disponible).")
            self._connected = bool(self.rtsp_fallback_url)
            return self._connected

        password = os.getenv(self._password_env, "")
        if not password:
            LOG.warning(
                "[ONVIFConnector] Variable de entorno '%s' no definida. "
                "Intentando sin contraseña.",
                self._password_env,
            )

        try:
            self._cam = _ONVIFCamera(
                self.host,
                self.port,
                self.user,
                password,
            )
            self._cam.update_xaddrs()
            self._connected = True
            LOG.info("[ONVIFConnector] Conectado a %s:%d OK", self.host, self.port)
            return True
        except Exception as exc:
            LOG.error("[ONVIFConnector] Error conectando a %s: %s", self.host, exc)
            self._connected = False
            return False

    # ── Stream URI ────────────────────────────────────────────────────────────

    def get_stream_uri(
        self,
        profile_index: int = 0,
        protocol: str = "RTSP",
    ) -> str:
        """Obtiene la URL del stream de video.

        Args:
            profile_index: Índice del perfil de video (0 = principal).
            protocol:      Protocolo de stream: "RTSP" | "HTTP".

        Returns:
            URL del stream (RTSP) o rtsp_fallback_url si ONVIF no disponible.
        """
        if not _ONVIF_AVAILABLE or self._cam is None:
            LOG.info("[ONVIFConnector] Usando fallback URL: %s", self.rtsp_fallback_url)
            return self.rtsp_fallback_url

        try:
            media = self._cam.create_media_service()
            profiles = media.GetProfiles()
            if not profiles:
                LOG.warning("[ONVIFConnector] Sin perfiles de media en %s", self.host)
                return self.rtsp_fallback_url

            idx     = min(profile_index, len(profiles) - 1)
            profile = profiles[idx]
            token   = profile.token

            stream_setup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": protocol},
            }
            uri_resp = media.GetStreamUri(
                {"StreamSetup": stream_setup, "ProfileToken": token}
            )
            uri = uri_resp.Uri
            LOG.info("[ONVIFConnector] Stream URI obtenido: %s (token=%s)", uri, token)
            return uri

        except Exception as exc:
            LOG.error("[ONVIFConnector] Error obteniendo StreamURI de %s: %s", self.host, exc)
            return self.rtsp_fallback_url

    # ── Device Info ───────────────────────────────────────────────────────────

    def get_device_info(self) -> Dict[str, str]:
        """Retorna información del dispositivo ONVIF.

        Returns:
            Dict con: manufacturer, model, firmware_version, serial_number, hardware_id.
        """
        if not _ONVIF_AVAILABLE or self._cam is None:
            return {
                "manufacturer": "unknown",
                "model": "unknown",
                "firmware_version": "unknown",
                "serial_number": "unknown",
                "hardware_id": "unknown",
                "source": "no_onvif",
            }

        try:
            device_svc = self._cam.create_devicemgmt_service()
            info = device_svc.GetDeviceInformation()
            return {
                "manufacturer":     getattr(info, "Manufacturer", "unknown"),
                "model":            getattr(info, "Model", "unknown"),
                "firmware_version": getattr(info, "FirmwareVersion", "unknown"),
                "serial_number":    getattr(info, "SerialNumber", "unknown"),
                "hardware_id":      getattr(info, "HardwareId", "unknown"),
                "source":           "onvif",
            }
        except Exception as exc:
            LOG.error("[ONVIFConnector] Error en GetDeviceInformation: %s", exc)
            return {"source": "error", "error": str(exc)}

    # ── PTZ ───────────────────────────────────────────────────────────────────

    def ptz_move(
        self,
        pan: float = 0.0,
        tilt: float = 0.0,
        zoom: float = 0.0,
        profile_index: int = 0,
    ) -> bool:
        """Mueve la cámara PTZ.

        Args:
            pan:   Velocidad horizontal [-1.0, 1.0]. Positivo = derecha.
            tilt:  Velocidad vertical  [-1.0, 1.0]. Positivo = arriba.
            zoom:  Velocidad de zoom   [-1.0, 1.0]. Positivo = acercar.
            profile_index: Índice del perfil PTZ.

        Returns:
            True si el comando se envió correctamente.
        """
        if not _ONVIF_AVAILABLE or self._cam is None:
            LOG.warning("[ONVIFConnector] PTZ no disponible — onvif-zeep requerido.")
            return False

        try:
            ptz = self._cam.create_ptz_service()
            media = self._cam.create_media_service()
            profiles = media.GetProfiles()
            idx = min(profile_index, len(profiles) - 1)
            token = profiles[idx].token

            velocity = {
                "PanTilt": {"x": pan, "y": tilt},
                "Zoom":    {"x": zoom},
            }
            ptz.ContinuousMove({"ProfileToken": token, "Velocity": velocity})
            LOG.info("[ONVIFConnector] PTZ move pan=%.2f tilt=%.2f zoom=%.2f", pan, tilt, zoom)
            return True

        except Exception as exc:
            LOG.error("[ONVIFConnector] Error PTZ en %s: %s", self.host, exc)
            return False

    def ptz_stop(self, profile_index: int = 0) -> bool:
        """Detiene el movimiento PTZ."""
        if not _ONVIF_AVAILABLE or self._cam is None:
            return False
        try:
            ptz = self._cam.create_ptz_service()
            media = self._cam.create_media_service()
            profiles = media.GetProfiles()
            token = profiles[min(profile_index, len(profiles) - 1)].token
            ptz.Stop({"ProfileToken": token, "PanTilt": True, "Zoom": True})
            return True
        except Exception as exc:
            LOG.error("[ONVIFConnector] Error PTZ stop: %s", exc)
            return False

    # ── Descubrimiento ────────────────────────────────────────────────────────

    @staticmethod
    def discover(timeout_sec: float = 5.0) -> List[str]:
        """Descubre cámaras ONVIF en la red local via WS-Discovery.

        Args:
            timeout_sec: Tiempo de espera para respuestas.

        Returns:
            Lista de IPs/hosts descubiertos.
        """
        if not _ONVIF_AVAILABLE:
            LOG.warning("[ONVIFConnector] Descubrimiento no disponible sin onvif-zeep.")
            return []

        try:
            from wsdiscovery import WSDiscovery, QName
            wsd = WSDiscovery()
            wsd.start()
            services = wsd.searchServices(timeout=timeout_sec)
            wsd.stop()
            hosts = []
            for svc in services:
                for addr in svc.getXAddrs():
                    if "onvif" in addr.lower():
                        # Extraer host de la URL ONVIF
                        from urllib.parse import urlparse
                        parsed = urlparse(addr)
                        if parsed.hostname:
                            hosts.append(parsed.hostname)
            LOG.info("[ONVIFConnector] Descubrimiento: %d cámara(s) encontrada(s)", len(hosts))
            return list(set(hosts))
        except ImportError:
            LOG.warning("[ONVIFConnector] wsdiscovery no instalado. pip install wsdiscovery")
            return []
        except Exception as exc:
            LOG.error("[ONVIFConnector] Error en WS-Discovery: %s", exc)
            return []

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def to_camera_info(self) -> ONVIFCameraInfo:
        """Retorna un ONVIFCameraInfo con los datos del dispositivo."""
        device = self.get_device_info()
        uri    = self.get_stream_uri()
        return ONVIFCameraInfo(
            host         = self.host,
            port         = self.port,
            stream_uri   = uri,
            manufacturer = device.get("manufacturer", "unknown"),
            model        = device.get("model", "unknown"),
            firmware     = device.get("firmware_version", "unknown"),
            serial_number= device.get("serial_number", "unknown"),
        )

    def close(self) -> None:
        self._cam      = None
        self._connected = False

    def __enter__(self) -> "ONVIFConnector":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
