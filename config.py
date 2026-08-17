"""Configuración del proyecto (valores por defecto seguros).

Este archivo lee variables de entorno para permitir configuraciones por
entorno (local, docker, CI). NO se deben guardar credenciales en el repo.

Usar la variable de entorno `GOOGLE_APPLICATION_CREDENTIALS` para apuntar al
JSON de la cuenta de servicio de Firebase.
"""
import os
from pathlib import Path
from typing import Final

# ============================================================================
# FIRESTORE CONFIGURATION
# ============================================================================

# Nombre de la colección Firestore (confirmado por ti)
FIRESTORE_COLLECTION: Final[str] = os.getenv("FIRESTORE_COLLECTION", "Prueba_Alertas")

# Ruta al JSONL local generado por JSONLogger (lee JSON legacy para compatibilidad)
JSON_LOG_PATH: Final[str] = os.getenv("JSON_LOG_PATH", str(Path("outputs") / "events_history.jsonl"))

# Ruta al archivo JSONL de eventos (NUEVO: reemplaza JSON_LOG_PATH)
EVENT_LOG_PATH: Final[str] = os.getenv("EVENT_LOG_PATH", str(Path("outputs") / "events_log.jsonl"))

# Intervalo en segundos para sincronizar con Firestore desde el hilo daemon
SYNC_INTERVAL: Final[int] = int(os.getenv("SYNC_INTERVAL", "10"))

# ============================================================================
# EVENT DEDUPLICATION & FILTERING (v2.0)
# ============================================================================

# Duración mínima de caída en segundos para ser considerada evento válido
# (evita falsos positivos por cambios transitorios)
MIN_FALL_DURATION_SEC: Final[float] = float(os.getenv("MIN_FALL_DURATION_SEC", "0.5"))

# Ventana de deduplicación: agrupa caídas dentro de este intervalo en una sola
EVENT_DEDUP_WINDOW_SEC: Final[float] = float(os.getenv("EVENT_DEDUP_WINDOW_SEC", "2.0"))

# Si está habilitado, usa EventLogger (frame-a-evento en lugar de frame-a-frame)
USE_EVENT_LOGGER: Final[bool] = os.getenv("USE_EVENT_LOGGER", "true").lower() in ["true", "1", "yes"]

# Modo servidor/Docker/Raspberry sin interfaz gráfica: no usar cv2.imshow/waitKey
HEADLESS_MODE: Final[bool] = os.getenv("HEADLESS_MODE", "false").lower() in ["true", "1", "yes"]

# NOTA: No ponemos la ruta de credenciales aquí. Use la variable de entorno
# GOOGLE_APPLICATION_CREDENTIALS para que firebase-admin la detecte.

# Fuente de video: puede ser un índice (webcam) o una URL (IP webcam e.g. http://10.0.0.2:8080/video)
# Por defecto usamos 0 (webcam por defecto). Se puede sobrescribir con la variable
# de entorno VIDEO_SOURCE.
VIDEO_SOURCE: Final[str] = os.getenv("VIDEO_SOURCE", "0")