# GUÍA DE PRUEBAS LOCALES: Vigilante Digital IA

**Objetivo:** Ejecutar análisis de video MP4 localmente, capturar métricas y documentar resultados.

---

## PARTE 1: PREPARAR EL ENTORNO

### 1.1 Estructura de directorios para videos y datos de prueba

```
VigilanteDigital_1.0/
├── main.py
├── config.py
├── requirements.txt
├── ...
│
├── tests/                          # (NUEVO) Carpeta de pruebas
│   └── test_videos/                # Videos MP4 para análisis
│       ├── fall_sample_01.mp4      # Video de prueba 1 (caída)
│       ├── normal_walk.mp4         # Video de prueba 2 (caminata normal)
│       └── README_test_videos.txt
│
├── test_outputs/                   # (NUEVO) Resultados de pruebas
│   ├── events_history.json
│   ├── .events_history.json.state
│   └── test_metrics.json
│
├── scripts/                        # (NUEVO) Scripts auxiliares
│   └── run_test.py                 # Script de pruebas con métricas
│
└── docs/
    ├── ANALYSIS.md                 # Este archivo
    ├── TEST_RESULTS.md             # Resultados de pruebas (genera aquí)
    └── ...
```

### 1.2 Crear carpetas

```powershell
mkdir tests\test_videos
mkdir test_outputs
mkdir scripts
```

### 1.3 Descargar video de prueba

**Opción A: Usar un video tuyo** (que descargaste)
- Coloca el archivo MP4 en: `tests/test_videos/fall_sample_01.mp4`
- Debe ser un video MP4 con resolución ≥ 720p (recomendado 1080p)

**Opción B: Descargar video de ejemplo**
- Dataset público de caídas: [UR Fall Detection Dataset](http://fenix.ur.edu.pl/~mkepski/ds/uf.html)
- Descarga un video (formato MP4) y colócalo en `tests/test_videos/`

**Opción C: Usar tu cámara en vivo**
- Modifica `main.py` para capturar de webcam: `VIDEO_PATH = 0`

---

## PARTE 2: SCRIPT DE PRUEBAS CON MÉTRICAS

Creo `scripts/run_test.py` (pronto lo crearé):

```python
# scripts/run_test.py
"""
Script de pruebas para Vigilante Digital IA.
Procesa un video MP4, captura métricas y registra resultados.

Uso:
    python scripts/run_test.py --video tests/test_videos/fall_sample_01.mp4 --output test_outputs/test_metrics.json
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import cv2

# Importar módulos del proyecto
from core.pose_detector import PoseDetector
from outputs.json_logger import JSONLogger
from outputs.firebase_connector import FirebaseConnector
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)


class VideoTestHarness:
    """Harness para ejecutar pruebas de video con captura de métricas."""

    def __init__(self, video_path: str, output_dir: str = "test_outputs"):
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Configuración para pruebas (overrides)
        self.json_log_path = self.output_dir / "events_history.json"
        self.metrics_path = self.output_dir / "test_metrics.json"

        # Métricas
        self.metrics = {
            "start_time": datetime.now().isoformat(),
            "video_path": str(self.video_path),
            "total_frames": 0,
            "total_falls_detected": 0,
            "avg_fps": 0.0,
            "min_fps": float('inf'),
            "max_fps": 0.0,
            "total_process_time": 0.0,
            "firebase_syncs": 0,
            "firebase_events_uploaded": 0,
            "errors": [],
            "end_time": None,
        }

        self.frame_times = []

    def run(self) -> bool:
        """Ejecuta la prueba completa."""
        try:
            # 1. Abrir video
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                raise RuntimeError(f"No se pudo abrir video: {self.video_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_video = cap.get(cv2.CAP_PROP_FPS)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            LOG.info(f"Video abierto: {total_frames} frames @ {fps_video:.2f} fps, {w}x{h}")
            self.metrics["video_fps"] = fps_video
            self.metrics["video_resolution"] = f"{w}x{h}"

            # 2. Inicializar componentes
            detector = PoseDetector(complexity=1, frame_scale=1.0)
            json_logger = JSONLogger(file_path=self.json_log_path)
            connector = FirebaseConnector(json_log_path=self.json_log_path, collection=config.FIRESTORE_COLLECTION)

            # 3. Procesar video
            frame_idx = 0
            fall_count = 0
            p_time = time.time()

            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    LOG.info("Fin del video")
                    break

                frame_start = time.time()

                # Detectar pose
                proc_frame, results = detector.find_pose(frame, draw=True)
                lm_list, bbox = detector.find_position(proc_frame, results, draw=True)

                # Lógica de caída
                if bbox:
                    aspect_ratio = bbox["height"] / max(1, bbox["width"])
                    if aspect_ratio < 0.8:
                        fall_count += 1
                        cv2.putText(proc_frame, f"CAIDA DETECTADA #{fall_count}", (bbox["xmin"], bbox["ymin"] - 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        
                        # Log evento
                        json_logger.log_event(
                            photo_path=str(self.output_dir / f"fall_{fall_count:03d}_frame_{frame_idx:06d}.jpg"),
                            event_type="fall",
                            metadata={"aspect_ratio": aspect_ratio, "frame_idx": frame_idx}
                        )
                        LOG.info(f"✓ Caída detectada en frame {frame_idx} (ratio={aspect_ratio:.2f})")

                # FPS
                c_time = time.time()
                fps = 1.0 / max(1e-6, (c_time - p_time))
                p_time = c_time
                self.frame_times.append(fps)
                self.metrics["max_fps"] = max(self.metrics["max_fps"], fps)
                self.metrics["min_fps"] = min(self.metrics["min_fps"], fps)

                cv2.putText(proc_frame, f'FPS: {int(fps)}', (20, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

                # Mostrar (sin bloquear)
                cv2.imshow("Test: Vigilante IA", cv2.resize(proc_frame, (1280, 720)))
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                frame_idx += 1

                # Cada 100 frames, imprimir progreso
                if frame_idx % 100 == 0:
                    LOG.info(f"Procesados {frame_idx}/{total_frames} frames ({100*frame_idx/total_frames:.1f}%)")

            cap.release()
            cv2.destroyAllWindows()

            # 4. Finalizar y sincronizar Firebase
            self.metrics["total_frames"] = frame_idx
            self.metrics["total_falls_detected"] = fall_count
            self.metrics["avg_fps"] = sum(self.frame_times) / len(self.frame_times) if self.frame_times else 0
            self.metrics["total_process_time"] = time.time() - p_time

            # Firebase sync
            LOG.info("Sincronizando eventos a Firebase...")
            uploaded = connector.sync_new_events()
            self.metrics["firebase_syncs"] = 1
            self.metrics["firebase_events_uploaded"] = uploaded
            LOG.info(f"✓ {uploaded} eventos subidos a Firestore")

            self.metrics["end_time"] = datetime.now().isoformat()
            self.metrics["success"] = True

            return True

        except Exception as exc:
            LOG.exception(f"Error durante prueba: {exc}")
            self.metrics["errors"].append(str(exc))
            self.metrics["end_time"] = datetime.now().isoformat()
            self.metrics["success"] = False
            return False

        finally:
            self.save_metrics()

    def save_metrics(self) -> None:
        """Guarda las métricas en JSON."""
        try:
            with open(self.metrics_path, "w", encoding="utf-8") as fh:
                json.dump(self.metrics, fh, indent=2, ensure_ascii=False)
            LOG.info(f"✓ Métricas guardadas en: {self.metrics_path}")
            
            # Imprimir resumen
            print("\n" + "="*60)
            print("RESUMEN DE PRUEBA")
            print("="*60)
            print(f"Video: {self.metrics['video_path']}")
            print(f"Total de frames: {self.metrics['total_frames']}")
            print(f"Caídas detectadas: {self.metrics['total_falls_detected']}")
            print(f"FPS promedio: {self.metrics['avg_fps']:.2f}")
            print(f"FPS min/max: {self.metrics['min_fps']:.2f}/{self.metrics['max_fps']:.2f}")
            print(f"Eventos subidos a Firebase: {self.metrics['firebase_events_uploaded']}")
            print(f"Estado: {'✓ EXITOSO' if self.metrics['success'] else '✗ CON ERRORES'}")
            print("="*60 + "\n")

        except Exception as exc:
            LOG.exception(f"Error guardando métricas: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Prueba Vigilante Digital IA con video local")
    parser.add_argument("--video", required=True, help="Ruta al archivo MP4")
    parser.add_argument("--output", default="test_outputs", help="Directorio de salida para métricas")
    args = parser.parse_args()

    harness = VideoTestHarness(video_path=args.video, output_dir=args.output)
    success = harness.run()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

---

## PARTE 3: CÓMO EJECUTAR LAS PRUEBAS

### Paso 1: Verificar que el video está en su lugar

```powershell
Get-ChildItem tests\test_videos\
```

Deberías ver tu archivo MP4.

### Paso 2: Configurar credenciales Firebase (sesión actual)

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\secrets\firebase-service-account.json"
```

### Paso 3: Ejecutar el script de pruebas

```powershell
python scripts/run_test.py --video tests/test_videos/fall_sample_01.mp4 --output test_outputs
```

**Salida esperada:**

```
2025-12-08 12:34:56 - __main__ - INFO - Video abierto: 512 frames @ 30.00 fps, 1920x1080
2025-12-08 12:34:56 - __main__ - INFO - Procesados 100/512 frames (19.5%)
2025-12-08 12:34:57 - __main__ - INFO - ✓ Caída detectada en frame 45 (ratio=0.72)
...
============================================================
RESUMEN DE PRUEBA
============================================================
Video: tests/test_videos/fall_sample_01.mp4
Total de frames: 512
Caídas detectadas: 2
FPS promedio: 18.34
FPS min/max: 14.2/22.1
Eventos subidos a Firebase: 2
Estado: ✓ EXITOSO
============================================================
```

### Paso 4: Ver resultados

**Métricas locales:**
```powershell
cat test_outputs\test_metrics.json
```

**Eventos en Firestore:**
1. Ve a [Firebase Console](https://console.firebase.google.com)
2. Selecciona proyecto `TU_PROYECTO_FIREBASE`
3. Firestore Database → Colección `Prueba_Alertas`
4. Verás documentos con los eventos detectados

---

## PARTE 4: DOCUMENTAR RESULTADOS

Después de ejecutar la prueba, crea `TEST_RESULTS.md`:

```markdown
# Resultados de Pruebas - Vigilante Digital IA

## Prueba 1: fall_sample_01.mp4

**Fecha:** 8 de Diciembre de 2025  
**Duración:** 17 segundos  
**Resolución:** 1920x1080  
**FPS video:** 30

### Métricas

- **Total frames procesados:** 512
- **Caídas detectadas:** 2
- **FPS promedio:** 18.34
- **FPS mín/máx:** 14.2/22.1
- **Eventos subidos a Firebase:** 2
- **Estado:** ✓ EXITOSO

### Análisis

- La detección funcionó correctamente
- 2 caídas verdaderas positivas
- 0 falsos positivos
- Firebase sincronizó correctamente

### Observaciones

- El video contiene personas caminando y 2 caídas simuladas
- MediaPipe detectó los landmarks correctamente
- La sincronización a Firebase fue exitosa
- Debería integrar YOLO para mejorar precisión en diferencia entre "sentarse" vs "caer"

### Siguiente paso

Evaluar YOLO para mejorar de ~60% a ~85-90% de precisión.
```

---

## PARTE 5: CASOS DE PRUEBA

| Caso | Video | Esperado | Validación |
|------|-------|----------|-----------|
| 1 | Persona caminando | 0 caídas | ✓ Si FPS estable |
| 2 | Persona sentándose | 0-1 falso positivo | ⚠ Depende timing |
| 3 | Caída simulada | ≥1 detección | ✓ Si ratio < 0.8 |
| 4 | Múltiples personas | Detecta todas | Pendiente test |

---

## PARTE 6: TROUBLESHOOTING

### Error: "No se pudo abrir el video"

```
Solución: Verifica que:
- El archivo MP4 existe
- La ruta es correcta (usa Path absoluto o relativo desde VigilanteDigital_1.0/)
- El codec es soportado por OpenCV (H.264, MPEG4)
```

### Error: "GOOGLE_APPLICATION_CREDENTIALS not found"

```
Solución:
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\ruta\correcta\firebase-service-account.json"
```

### FPS muy bajo (< 10)

```
Soluciones:
- Reduce resolución: cv2.resize(frame, (1280, 720))
- Usa frame_scale=0.5: PoseDetector(complexity=1, frame_scale=0.5)
- Reduce complexity a 0: PoseDetector(complexity=0)
```

### No aparecen eventos en Firestore

```
Verificar:
1. ¿La variable GOOGLE_APPLICATION_CREDENTIALS está configurada?
2. ¿El JSON corresponde al proyecto TU_PROYECTO_FIREBASE?
3. ¿Firestore tiene la colección "Prueba_Alertas" creada?
4. ¿Hay errores en logs de console?
```

---

## PRÓXIMOS PASOS

1. Ejecutar prueba y documentar resultados
2. Si precisión es baja → integrar YOLO
3. Agregar más casos de prueba (múltiples personas, luz baja, etc.)
4. Escribir tests unitarios
