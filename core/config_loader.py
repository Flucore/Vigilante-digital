"""Cargador de configuración jerárquico para Vigilante Digital.

Precedencia (de mayor a menor):
  1. Variables de Entorno (.env / shell)
  2. Archivo JSON del cliente (client_config.json)
  3. Valores por defecto (config.py)

No hay credenciales en ningún archivo del repositorio.
Las URLs de cámaras, contraseñas SMTP y tokens se leen siempre desde
variables de entorno referenciadas en el JSON por campos *_env.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Python 3.9+
except ImportError:  # pragma: no cover
    try:
        from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # type: ignore
    except ImportError:
        ZoneInfo = None  # type: ignore
        ZoneInfoNotFoundError = Exception  # type: ignore

LOG = logging.getLogger(__name__)

# Claves obligatorias en el JSON del cliente
_REQUIRED_KEYS: frozenset = frozenset({"_schema_version", "schedule", "cameras"})


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses de configuración
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ZoneConfig:
    """Zona de detección (polígono M0 / línea / ROI) dentro de una cámara.

    type (M0): polygon | geofence | pool | wall | coop | machine_yard | custom
    type (otros): line | roi
    points: coordenadas; si normalized=True están en [0, 1] relativos al frame.
    """

    id: str
    label: str
    type: str
    critical: bool = False
    points: List[List[float]] = field(default_factory=list)
    normalized: bool = True


@dataclass
class CameraConfig:
    """Configuración resuelta de una cámara individual."""

    id: str
    name: str
    stream_url: str         # URL resuelta desde env o valor directo
    zone: str
    sector: str
    enabled: bool
    modules_active: List[str]
    alert_level_after_hours: int   # 1=log, 2=notify, 3=critical(bocina)
    zones: List[ZoneConfig]
    raw: Dict[str, Any]    # dict original para parámetros específicos del módulo


@dataclass
class ScheduleConfig:
    """Configuración de horario hábil del cliente."""

    timezone: str
    work_days: List[int]    # 0=Lunes … 6=Domingo
    start_time: str         # "HH:MM"
    end_time: str           # "HH:MM"
    holidays: List[str]     # ["YYYY-MM-DD", ...]


# ──────────────────────────────────────────────────────────────────────────────
# ConfigLoader
# ──────────────────────────────────────────────────────────────────────────────

class ConfigLoader:
    """Carga y valida la configuración del cliente con precedencia jerárquica.

    Uso::

        loader = ConfigLoader(Path("client_config.json"))
        cameras = loader.get_cameras()
        schedule = loader.get_schedule()
        after_hours = is_after_hours(schedule)
    """

    def __init__(self, config_path: Union[str, Path]) -> None:
        self._path = Path(config_path)
        self._raw: Dict[str, Any] = {}
        self._load()

    # ── carga y validación ────────────────────────────────────────────────────

    def _load(self) -> None:
        """Lee el JSON, valida estructura mínima y loggea el resumen."""
        if not self._path.exists():
            raise FileNotFoundError(
                f"\n[ConfigLoader] Archivo no encontrado: {self._path}\n"
                f"  Crea el archivo o usa --config para especificar la ruta."
            )

        try:
            with self._path.open("r", encoding="utf-8") as f:
                self._raw = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"\n[ConfigLoader] Sintaxis inválida en '{self._path}' "
                f"(línea {exc.lineno}): {exc.msg}\n"
                f"  Verifica que el JSON sea válido."
            ) from exc

        missing = _REQUIRED_KEYS - set(self._raw.keys())
        if missing:
            raise ValueError(
                f"\n[ConfigLoader] Faltan campos obligatorios en '{self._path}':\n"
                f"  {', '.join(sorted(missing))}\n"
                f"  Consulta MASTER_DEVELOPMENT_PLAN.md sección 4.2 para el esquema completo."
            )

        schema = self._raw.get("_schema_version", "?")
        if not str(schema).startswith("2"):
            LOG.warning(
                "[ConfigLoader] schema_version='%s' — se esperaba '2.x'. "
                "Algunas funciones pueden no operar correctamente.",
                schema,
            )

        n_cameras = len([c for c in self._raw.get("cameras", []) if c.get("enabled", True)])
        LOG.info(
            "[ConfigLoader] Configuración cargada | cliente='%s' | schema='%s' | cámaras_activas=%d",
            self._raw.get("_client_name", "desconocido"),
            schema,
            n_cameras,
        )

    # ── resolución de valores desde entorno ──────────────────────────────────

    def _resolve_url(self, cam_raw: Dict[str, Any]) -> str:
        """Resuelve URL del stream: env > stream_url directo."""
        env_key = cam_raw.get("stream_url_env")
        if env_key:
            url_from_env = os.getenv(env_key, "")
            if url_from_env:
                return url_from_env
            # Fallback a valor directo si existe (útil en dev local)
            direct = cam_raw.get("stream_url", "")
            if direct:
                LOG.debug(
                    "[ConfigLoader] Cámara '%s': env '%s' no definida; usando stream_url directo.",
                    cam_raw.get("id"), env_key,
                )
                return direct
            LOG.warning(
                "[ConfigLoader] Cámara '%s': env '%s' no definida y sin stream_url fallback.",
                cam_raw.get("id"), env_key,
            )
            return ""
        return cam_raw.get("stream_url", "")

    # ── accesores públicos ────────────────────────────────────────────────────

    def get_cameras(self) -> List[CameraConfig]:
        """Retorna las cámaras habilitadas con sus URLs resueltas."""
        cameras: List[CameraConfig] = []
        for cam_raw in self._raw.get("cameras", []):
            if not cam_raw.get("enabled", True):
                continue

            zones = [
                ZoneConfig(
                    id=z.get("id", f"zone_{i}"),
                    label=z.get("label", ""),
                    type=z.get("type", "polygon"),
                    critical=bool(z.get("critical", False)),
                    points=z.get("points", []),
                    normalized=bool(z.get("normalized", True)),
                )
                for i, z in enumerate(cam_raw.get("zones", []))
            ]

            cameras.append(CameraConfig(
                id=cam_raw.get("id", "CAM"),
                name=cam_raw.get("name", cam_raw.get("id", "CAM")),
                stream_url=self._resolve_url(cam_raw),
                zone=cam_raw.get("zone", ""),
                sector=cam_raw.get("sector", ""),
                enabled=bool(cam_raw.get("enabled", True)),
                modules_active=cam_raw.get("modules_active", ["fall_detection"]),
                alert_level_after_hours=int(cam_raw.get("alert_level_after_hours", 1)),
                zones=zones,
                raw=cam_raw,
            ))
        return cameras

    def load_camera_config(self, cam_id: str) -> Optional[CameraConfig]:
        """Retorna la configuración de una cámara por ID. None si no existe."""
        for cam in self.get_cameras():
            if cam.id == cam_id:
                return cam
        LOG.warning("[ConfigLoader] Cámara '%s' no encontrada en la configuración.", cam_id)
        return None

    def get_schedule(self) -> ScheduleConfig:
        """Retorna la configuración de horario del cliente."""
        s = self._raw.get("schedule", {})
        return ScheduleConfig(
            timezone=s.get("timezone", "America/Santiago"),
            work_days=s.get("work_days", [0, 1, 2, 3, 4]),
            start_time=s.get("start_time", "08:00"),
            end_time=s.get("end_time", "17:00"),
            holidays=s.get("holidays", []),
        )

    def get_section(self, key: str, default: Any = None) -> Any:
        """Retorna una sección completa de la config por clave."""
        return self._raw.get(key, default)

    def get_client_id(self) -> str:
        """Retorna el ID del cliente."""
        return self._raw.get("_client_id", "UNKNOWN")

    def get_schema_version(self) -> str:
        """Retorna la versión del esquema de configuración."""
        return str(self._raw.get("_schema_version", "2.0"))


# ──────────────────────────────────────────────────────────────────────────────
# Evaluador de horario
# ──────────────────────────────────────────────────────────────────────────────

def is_after_hours(schedule: ScheduleConfig) -> bool:
    """Determina si el momento actual está fuera del horario hábil configurado.

    Args:
        schedule: Configuración de horario del cliente (desde ConfigLoader).

    Returns:
        True si es horario no hábil (noche, fin de semana, feriado o fuera del
        rango horario laboral). False si es horario hábil.

    Ejemplo::

        schedule = loader.get_schedule()
        if is_after_hours(schedule):
            trigger_horn_alarm()
    """
    # Resolver timezone
    tz = None
    if ZoneInfo is not None:
        try:
            tz = ZoneInfo(schedule.timezone)
        except (ZoneInfoNotFoundError, Exception):
            LOG.warning(
                "[is_after_hours] Timezone '%s' no reconocida; usando UTC.",
                schedule.timezone,
            )
            tz = ZoneInfo("UTC") if ZoneInfo is not None else None

    now = datetime.now(tz) if tz is not None else datetime.utcnow()

    # 1. Día de la semana (0=Lunes, 6=Domingo)
    if now.weekday() not in schedule.work_days:
        return True

    # 2. Feriados
    today_str = now.strftime("%Y-%m-%d")
    if today_str in (schedule.holidays or []):
        return True

    # 3. Rango horario
    try:
        sh, sm = [int(x) for x in schedule.start_time.split(":")]
        eh, em = [int(x) for x in schedule.end_time.split(":")]
    except (ValueError, AttributeError):
        LOG.warning("[is_after_hours] Formato de horario inválido; asumiendo horario hábil.")
        return False

    start_min = sh * 60 + sm
    end_min   = eh * 60 + em
    now_min   = now.hour * 60 + now.minute

    return now_min < start_min or now_min >= end_min
