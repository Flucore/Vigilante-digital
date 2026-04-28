"""Gestión de datasets para aprendizaje incremental supervisado por humano.

Este módulo no entrena modelos por sí solo. Su función es ordenar evidencia:
- guardar imágenes bajo una etiqueta,
- registrar metadata de contexto,
- producir manifiestos JSONL compatibles con pipelines futuros.

La filosofía es "human-in-the-loop": el humano valida, etiqueta y promueve
ejemplos a dataset antes de entrenar modelos YOLO/segmentación.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class DatasetSample:
    """Registro canónico de una muestra etiquetada."""

    sample_id: str
    label: str
    image_path: str
    source_path: str
    created_at: str
    reviewer: str
    notes: str
    metadata: Dict[str, Any]


class LearningDataset:
    """Administra imágenes etiquetadas para entrenamiento futuro."""

    def __init__(self, root_dir: str | Path = "datasets/vigilante") -> None:
        self.root_dir = Path(root_dir)
        self.images_dir = self.root_dir / "images"
        self.manifest_path = self.root_dir / "manifest.jsonl"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def add_image(
        self,
        source_path: str | Path,
        label: str,
        reviewer: str = "human",
        notes: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DatasetSample:
        """Copia una imagen al dataset y agrega una línea al manifiesto."""
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {src}")

        safe_label = _safe_name(label)
        label_dir = self.images_dir / safe_label
        label_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        sample_id = f"{safe_label}_{ts}_{src.stem}"
        dest = label_dir / f"{sample_id}{src.suffix.lower()}"
        shutil.copy2(src, dest)

        sample = DatasetSample(
            sample_id=sample_id,
            label=label,
            image_path=str(dest),
            source_path=str(src),
            created_at=datetime.now(timezone.utc).isoformat(),
            reviewer=reviewer,
            notes=notes,
            metadata=metadata or {},
        )
        self._append_manifest(sample)
        return sample

    def _append_manifest(self, sample: DatasetSample) -> None:
        with self.manifest_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.lower())
    return cleaned.strip("_") or "unlabeled"
