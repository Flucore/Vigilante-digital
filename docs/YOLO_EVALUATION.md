# EVALUACIÓN: Integración de YOLO en Vigilante Digital IA

**Documento:** Propuesta Técnica  
**Fecha:** 8 de Diciembre de 2025  
**Estado:** Análisis Previo a Implementación

---

## 1. RESUMEN EJECUTIVO

Se evalúa la integración de **YOLOv8** (detección de objetos) junto con **MediaPipe Pose** (estimación de pose) para mejorar la precisión de detección de caídas de ~60% (solo ratio de aspecto) a **85-90%** (clasificación mediante deep learning).

**Recomendación:** Implementar en dos fases:
1. **Fase 1:** Baseline con MediaPipe actual (hoy)
2. **Fase 2:** Integrar YOLO v8 (después de validar baseline)

---

## 2. PROBLEMA ACTUAL

### Limitación de MediaPipe solo

**Método actual:** Ratio de aspecto (height/width < 0.8)

```python
aspect_ratio = bbox["height"] / bbox["width"]
if aspect_ratio < 0.8:
    # Detectar como "caída"
```

**Problemas:**
- **Falsos positivos:** 30-40%
  - Persona sentándose → ratio ~0.7 → falsa alarma
  - Persona agachándose → ratio ~0.75 → falsa alarma
  - Persona inclinada trabajando → ratio ~0.8 → falsa alarma

- **Falsos negativos:** 10-20%
  - Caída donde persona queda sentada (no tumbada) → ratio > 0.8
  - Caída parcialmente fuera de cámara

- **Sin contexto temporal:** Un solo frame anómalo activa alarma (no considera persistencia)

**Impacto:** Sistema no confiable para cliente final; requiere validación manual de alertas.

---

## 3. SOLUCIÓN: YOLO + MediaPipe

### Arquitectura Propuesta (Enfoque Híbrido)

```
Frame de video
  ↓
┌─────────────────────────────────────────┐
│  MediaPipe Pose (Ligero, 20-30 fps)     │
│  - Extrae landmarks esqueléticos        │
│  - Calcula bounding box                 │
│  - Rápido, bajo costo computacional     │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  YOLO v8 (Pesado pero preciso)          │
│  - Detecta clase: "Persona tumbada"     │
│  - Detecta clase: "Persona de pie"      │
│  - Detecta clase: "Persona sentada"     │
│  - Confianza > threshold (0.7)          │
└─────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────┐
│  Validación Temporal (Buffer)           │
│  - Requiere N frames consecutivos       │
│    con clase "Persona tumbada"          │
│  - Reduce falsos positivos              │
└─────────────────────────────────────────┘
  ↓
Decisión: "CAÍDA CONFIRMADA" o "NO"
  ↓
Si CAÍDA:
  - JSONLogger.log_event()
  - Firebase upload
  - Alerta SMS/Email (futuro)
```

### Ventajas

| Aspecto | Mejora |
|--------|--------|
| **Precisión** | 60% → 85-90% |
| **Falsos positivos** | 40% → 5-10% |
| **Confiabilidad** | Baja → Alta |
| **Contexto** | Solo ratio → Clasificación + temporal |
| **Mantenibilidad** | Heurística → ML entrenado |

### Desventajas

| Aspecto | Costo |
|--------|-------|
| **FPS** | 20-30 (MediaPipe) → 10-15 (MediaPipe + YOLO) |
| **Memoria** | ~250MB → ~600MB |
| **GPU** | Opcional → Casi obligatorio |
| **Latencia** | ~50ms → ~100-150ms por frame |
| **Complejidad** | Bajo → Medio |

---

## 4. OPCIONES DE IMPLEMENTACIÓN

### Opción A: YOLO v8 Nano (Ligero)

**Modelo:** `yolov8n.pt` (~6.3 MB)

```python
from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # Pre-entrenado en COCO

# Usar modelo genérico COCO
# Detecta 80 clases (person, chair, etc.)
results = model(frame)
```

**Pros:**
- Rápido (~30 fps en CPU, ~60+ fps en GPU)
- Bajo overhead de memoria
- Fácil de implementar

**Contras:**
- No está entrenado específicamente para "caídas"
- Detecta "persona" pero no distingue "tumbada" vs "de pie"
- Precisión moderada para nuestro caso

**Recomendación:** NO es suficiente para producción.

---

### Opción B: YOLO v8 Custom Trained (Recomendado)

**Crear dataset y entrenar modelo YOLO específico para nuestro problema:**

```python
# 1. Recopilar datos (200-500 imágenes)
# - Personas tumbadas (caídas)
# - Personas de pie
# - Personas sentadas
# - Diferentes ángulos, iluminación, etc.

# 2. Anotar con Roboflow o LabelImg

# 3. Entrenar modelo
from ultralytics import YOLO
model = YOLO('yolov8m.pt')
results = model.train(
    data='dataset.yaml',
    epochs=50,
    imgsz=640,
    device=0  # GPU
)

# 4. Usar modelo entrenado
custom_model = YOLO('runs/detect/train/weights/best.pt')
results = custom_model(frame)
```

**Pros:**
- Precisión específica para nuestro caso (85-95%)
- Más rápido que v8m/v8l
- Controlable y reproducible

**Contras:**
- Requiere dataset de calidad
- Requiere GPU para entrenar (~2-4 horas)
- Necesita validación/testing

**Recomendación:** MEJOR opción para producción.

---

### Opción C: YOLO v8 Medium/Large + Fine-tuning

**Usar modelo preentrenado más grande y ajustar:**

```python
model = YOLO('yolov8m.pt')  # o yolov8l.pt
results = model.train(
    data='dataset.yaml',
    epochs=20,  # Menos épocas (ya está entrenado)
    imgsz=640,
    device=0
)
```

**Pros:**
- Mejor base (mayor precisión general)
- Menos épocas de entrenamiento

**Contras:**
- Más lento (12-20 fps CPU, 40+ fps GPU)
- Más memoria (~600MB+)

**Recomendación:** Si hay GPU disponible en cliente.

---

## 5. IMPLEMENTACIÓN PROPUESTA

### Fase 1: Baseline (HOY)
- ✓ Ejecutar pruebas con MediaPipe actual
- ✓ Documentar falsos positivos/negativos
- ✓ Evaluar si es aceptable para cliente

### Fase 2: YOLO Integration (Próxima 1-2 semanas)

Si Fase 1 muestra baja precisión:

1. **Recopilar dataset** (3-5 días)
   - 300-500 imágenes de caídas simuladas/reales
   - 300-500 imágenes de personas normales

2. **Anotar imágenes** (2-3 días)
   - Usar Roboflow (gratuito para proyectos pequeños)
   - Crear bounding boxes con clases: "fall", "normal"

3. **Entrenar modelo YOLO** (1 día)
   - Usar YOLOv8m o YOLOv8n
   - 50 épocas, GPU recomendado
   - Validación cruzada

4. **Integrar en `core/`** (1 día)
   - Crear `core/yolo_detector.py`
   - Refactorizar `main.py` para usar ambos modelos

5. **Pruebas y validación** (2-3 días)
   - Ejecutar con dataset de prueba
   - Comparar con MediaPipe solo
   - Ajustar thresholds

---

## 6. CÓDIGO DE EJEMPLO (Futura Integración)

### Módulo: `core/yolo_detector.py`

```python
from ultralytics import YOLO
from typing import Dict, Any, Optional

class YOLOFallDetector:
    """Detector de caídas basado en YOLO entrenado."""

    def __init__(self, model_path: str = "models/yolo_fall.pt", confidence: float = 0.7):
        """
        Args:
            model_path: Ruta al modelo YOLO entrenado
            confidence: Threshold de confianza
        """
        self.model = YOLO(model_path)
        self.confidence = confidence

    def detect(self, frame) -> Dict[str, Any]:
        """Detecta caídas en un frame.

        Returns:
            {
                "is_fall": bool,
                "confidence": float,
                "bboxes": List,
                "raw_results": results
            }
        """
        results = self.model(frame, conf=self.confidence)[0]

        # Procesar resultados
        is_fall = False
        max_conf = 0.0
        for r in results.boxes:
            class_id = int(r.cls[0])
            conf = float(r.conf[0])
            class_name = self.model.names[class_id]

            if class_name == "fall" and conf > max_conf:
                is_fall = True
                max_conf = conf

        return {
            "is_fall": is_fall,
            "confidence": max_conf,
            "bboxes": results.boxes,
            "raw_results": results
        }
```

### Integración en `main.py`

```python
from core.pose_detector import PoseDetector
from core.yolo_detector import YOLOFallDetector

# Inicializar
pose_detector = PoseDetector(complexity=1)
yolo_detector = YOLOFallDetector(model_path="models/yolo_fall.pt")

# En loop principal
proc_frame, pose_results = pose_detector.find_pose(frame, draw=True)
yolo_result = yolo_detector.detect(proc_frame)

if yolo_result["is_fall"]:
    # Validación temporal (requiere N frames consecutivos)
    fall_count += 1
    json_logger.log_event(
        photo_path=f"fall_{frame_idx}.jpg",
        event_type="fall",
        metadata={"yolo_confidence": yolo_result["confidence"]}
    )
```

---

## 7. COMPARATIVA DE RENDIMIENTO

| Métrica | MediaPipe Solo | + YOLO Nano | + YOLO Medium |
|---------|---|---|---|
| **FPS (CPU)** | 20-30 | 15-20 | 10-15 |
| **Precisión** | ~60% | ~75% | ~90% |
| **Falsos + (%)** | 30-40 | 15-20 | 5-10 |
| **Memoria** | 250MB | 400MB | 600MB |
| **GPU necesario** | No | Opcional | Recomendado |

---

## 8. RECOMENDACIÓN FINAL

### Para Pruebas Iniciales (HOY):
✓ Usar **MediaPipe solo**
- Establecer baseline
- Documentar casos de falso positivo
- Evaluar si cliente acepta precisión ~60%

### Para Producción (Próximas 2 semanas):
✓ Implementar **YOLO v8 Custom Trained**
- Recopilar dataset específico
- Entrenar modelo personalizado
- Integrar con contexto temporal
- Lograr ~85-90% precisión

### Stack Final (Recomendado):

```
MediaPipe Pose (Rápido, contexto esquelético)
    ↓ (landmarks)
YOLO v8 Custom (Clasificación precisa: "fall" vs "normal")
    ↓ (confidence)
Validación Temporal (N frames consecutivos)
    ↓
Alerta + Firebase
```

**Ventaja clave:** MediaPipe proporciona contexto esquelético que YOLO puede usar; YOLO valida con precisión que realmente es una caída.

---

## 9. PLAN DE ACCIÓN

```
Hoy (8 de Dic):
├─ [x] Ejecutar baseline MediaPipe
├─ [x] Documentar resultados
├─ [ ] Recibir feedback de pruebas
└─ [ ] Decidir si procede con YOLO

Si precisión < 70% → YOLO
├─ Semana 1: Recopilar/anotar dataset
├─ Semana 2: Entrenar modelo
├─ Semana 2: Integrar y validar
└─ Semana 3: Deploy a cliente

Si precisión > 75% → Mantener MediaPipe
├─ Optimizar para cliente
├─ Agregar alertas SMS/Email
└─ Deploy directo
```

---

## CONCLUSIÓN

**YOLO es altamente recomendable para mejorar de 60% a 85-90% de precisión**, pero requiere:
1. Dataset específico de caídas
2. Tiempo de entrenamiento (GPU)
3. Validación y testing

**Propuesta:** Validar baseline primero; si es insuficiente, proceder con YOLO inmediatamente.
