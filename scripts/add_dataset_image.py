"""Agrega imágenes etiquetadas al dataset de aprendizaje supervisado.

Uso:
    python scripts/add_dataset_image.py --image test_outputs/snapshots/foto.jpg --label fall --reviewer valen
    python scripts/add_dataset_image.py --image foto.jpg --label traffic_green --notes "luz frontal"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.learning_dataset import LearningDataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Agregar imagen etiquetada al dataset")
    parser.add_argument("--image", required=True, help="Ruta a la imagen")
    parser.add_argument("--label", required=True, help="Etiqueta humana: fall, normal, red_shirt, etc.")
    parser.add_argument("--reviewer", default="human", help="Nombre de quien revisa/etiqueta")
    parser.add_argument("--notes", default="", help="Notas libres")
    parser.add_argument("--dataset", default="datasets/vigilante", help="Directorio raíz del dataset")
    args = parser.parse_args()

    dataset = LearningDataset(args.dataset)
    sample = dataset.add_image(
        source_path=args.image,
        label=args.label,
        reviewer=args.reviewer,
        notes=args.notes,
        metadata={"source": "manual_cli"},
    )
    print(f"Sample agregado: {sample.sample_id}")
    print(f"Imagen: {sample.image_path}")
    print(f"Manifest: {dataset.manifest_path}")


if __name__ == "__main__":
    main()
