"""Connector to sync local JSON events to Firestore.

This module does NOT contain credentials. It reads paths and settings from
`config.py` or from constructor parameters. Follow ARCHITECTURE.md rules: keep
credentials out of source and use environment variables or `config.py`.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except Exception:  # pragma: no cover - import may fail in environments without firebase-admin
    firebase_admin = None  # type: ignore
    credentials = None  # type: ignore
    firestore = None  # type: ignore

import config

logger = logging.getLogger(__name__)


class FirebaseConnector:
    """Synchronizes local JSON events into Firestore.

    Configuration (preferred in `config.py` or passed to constructor):
      - FIREBASE_CREDENTIALS_PATH: path to service account JSON (optional if using
        ADC / env var `GOOGLE_APPLICATION_CREDENTIALS`).
      - FIREBASE_PROJECT_ID: optional project id.
      - FIRESTORE_COLLECTION: collection name (default: "events").
      - JSON_LOG_PATH: path to JSON history written by `JSONLogger`.

    The connector keeps a small state file recording the ISO timestamp of the
    last-uploaded event to avoid duplicates.
    """

    def __init__(
        self,
        credentials_path: Optional[Union[str, Path]] = None,
        collection: Optional[str] = None,
        json_log_path: Optional[Union[str, Path]] = None,
        state_path: Optional[Union[str, Path]] = None,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ) -> None:
        self.logger = logger

        # Resolve config values (constructor args override config.py)
        cfg_cred = getattr(config, "FIREBASE_CREDENTIALS_PATH", None)
        cfg_proj = getattr(config, "FIREBASE_PROJECT_ID", None)
        cfg_collection = getattr(config, "FIRESTORE_COLLECTION", None)
        cfg_json_log = getattr(config, "JSON_LOG_PATH", None)

        self.credentials_path: Optional[Path] = Path(credentials_path) if credentials_path else (Path(cfg_cred) if cfg_cred else None)
        self.project_id: Optional[str] = cfg_proj
        self.collection: str = collection or cfg_collection or "events"
        self.json_log_path: Path = Path(json_log_path or cfg_json_log or "events_history.json")
        self.state_path: Path = Path(state_path or (self.json_log_path.parent / f".{self.json_log_path.name}.state"))

        self.max_retries = max_retries
        self.retry_backoff = float(retry_backoff)

        self._lock = threading.Lock()
        self.client = None
        self._init_firebase()

    def _init_firebase(self) -> None:
        """Initializes firebase-admin and Firestore client if possible.

        If credentials are not provided, tries to initialize with application
        default credentials (ADC). If initialization fails, `self.client` is
        left as None and methods become no-ops (they log accordingly).
        """
        if firebase_admin is None or credentials is None or firestore is None:
            self.logger.warning("firebase_admin not available; Firestore disabled")
            self.client = None
            return

        try:
            if self.credentials_path:
                cred = credentials.Certificate(str(self.credentials_path))
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(cred, {"projectId": self.project_id} if self.project_id else None)
            else:
                # Try default credentials (ADC) — respects GOOGLE_APPLICATION_CREDENTIALS env var
                if not firebase_admin._apps:
                    firebase_admin.initialize_app()

            self.client = firestore.client()
        except Exception as exc:
            self.logger.exception("Failed to initialize Firebase admin: %s", exc)
            self.client = None

    def _read_history(self) -> List[Dict[str, Any]]:
        """Reads the JSON history file produced by JSONLogger.

        Returns an empty list on errors.
        """
        try:
            if not self.json_log_path.exists():
                return []
            with self.json_log_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return data
            self._backup_corrupt_file("not-a-list")
            return []
        except json.JSONDecodeError:
            self._backup_corrupt_file("json-decode-error")
            return []
        except Exception:
            self.logger.exception("Error reading JSON history %s", self.json_log_path)
            return []

    def _backup_corrupt_file(self, reason: str) -> None:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_name = f"{self.json_log_path.name}.corrupt.{reason}.{ts}"
            backup_path = self.json_log_path.with_name(backup_name)
            os.replace(self.json_log_path, backup_path)
            self.logger.warning("Backed up corrupt JSON to %s", backup_path)
        except Exception:
            self.logger.exception("Failed to backup corrupt JSON file")

    def _read_state(self) -> Optional[str]:
        try:
            if not self.state_path.exists():
                return None
            with self.state_path.open("r", encoding="utf-8") as fh:
                return fh.read().strip() or None
        except Exception:
            self.logger.exception("Error reading state file %s", self.state_path)
            return None

    def _write_state(self, last_ts: str) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.state_path.parent))
            os.close(fd)
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(last_ts)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, str(self.state_path))
        except Exception:
            self.logger.exception("Error writing state file %s", self.state_path)

    @staticmethod
    def _parse_iso(ts: str) -> Optional[datetime]:
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    def _upload_event(self, event: Dict[str, Any]) -> bool:
        """Uploads a single event to Firestore with retries.

        Returns True on success, False otherwise.
        """
        if self.client is None:
            self.logger.debug("Firestore client not initialized; skipping upload")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                to_store = dict(event)
                # Use server timestamp for upload time
                to_store.setdefault("uploaded_at", firestore.SERVER_TIMESTAMP)
                self.client.collection(self.collection).add(to_store)
                return True
            except Exception as exc:
                self.logger.warning("Upload failed (attempt %d/%d): %s", attempt, self.max_retries, exc)
                time.sleep(self.retry_backoff * attempt)
        return False

    def sync_new_events(self) -> int:
        """Synchronize new events from the local JSON file to Firestore.

        Returns the number of events uploaded.
        """
        with self._lock:
            history = self._read_history()
            if not history:
                return 0

            last_state = self._read_state()
            last_dt = self._parse_iso(last_state) if last_state else None

            candidates: List[Tuple[datetime, Dict[str, Any]]] = []
            for ev in history:
                # Normalizar: EventLogger emite start_time, JSONLogger emite timestamp
                ts = ev.get("timestamp") or ev.get("start_time")
                if not ts:
                    continue
                ev_dt = self._parse_iso(ts)
                if ev_dt is None:
                    continue
                if last_dt is None or ev_dt > last_dt:
                    # Garantizar que el doc a subir tenga campo "timestamp"
                    normalized = dict(ev)
                    if "timestamp" not in normalized:
                        normalized["timestamp"] = ts
                    candidates.append((ev_dt, normalized))

            # Sort by timestamp ascending
            candidates.sort(key=lambda x: x[0])

            uploaded = 0
            for ev_dt, ev in candidates:
                if self._upload_event(ev):
                    uploaded += 1
                    # Update state after each successful upload
                    try:
                        self._write_state(ev_dt.isoformat())
                    except Exception:
                        self.logger.exception("Failed to write state after upload")

            return uploaded
