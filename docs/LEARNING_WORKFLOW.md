# Flujo de Aprendizaje Human-in-the-Loop

## Objetivo

Permitir que el sistema aprenda de imágenes reales cargadas por el humano, sin prometer entrenamiento automático prematuro. La primera versión organiza imágenes, etiquetas y metadata; la siguiente etapa exporta a YOLO y entrena modelos.

## Flujo Actual Implementado

```text
Evento detectado
    ↓
Snapshot en test_outputs/snapshots
    ↓
Humano revisa la imagen
    ↓
Humano etiqueta con scripts/add_dataset_image.py
    ↓
Imagen copiada a datasets/vigilante/images/<label>
    ↓
Registro agregado a datasets/vigilante/manifest.jsonl
```

## Comando para Cargar Imagen

```powershell
python scripts/add_dataset_image.py `
  --image test_outputs/snapshots/CAM_1_fall_20260428_010000.jpg `
  --label fall `
  --reviewer valen `
  --notes "caida simulada demo, iluminacion buena"
```

## Etiquetas Iniciales

### Caídas

- `fall`
- `normal`
- `sitting`
- `bending`
- `lying_no_fall`

### Polera Roja

- `red_shirt`
- `not_red_shirt`
- `red_object_false_positive`

### Semáforo/Luz

- `traffic_red`
- `traffic_yellow`
- `traffic_green`
- `traffic_off`
- `traffic_ambiguous`

### Perímetro

- `perimeter_breach`
- `perimeter_normal`

### Futuro

- `weapon`
- `tool`
- `helmet`
- `no_helmet`
- `thermal_hotspot`
- `thermal_coldspot`

## Reglas de Etiquetado

1. Etiquetar solo imágenes claras.
2. Si hay duda, usar etiqueta `ambiguous`.
3. Guardar falsos positivos como dataset útil.
4. Guardar falsos negativos manualmente si el sistema no detectó el evento.
5. No cargar imágenes sensibles sin consentimiento o base legal.

## Próxima Etapa

### Exportador YOLO

Crear script:

```text
scripts/export_yolo_dataset.py
```

Debe convertir `manifest.jsonl` a:

```text
datasets/yolo/
  images/train
  images/val
  labels/train
  labels/val
  data.yaml
```

### Anotación con Segmentación

Para objetos y EPP se requiere bounding box o máscara:

- usar CVAT/Label Studio,
- o integrar SAM para generar máscara asistida,
- luego exportar a YOLOv8 detect/seg.

## Principio

El sistema aprende cuando el humano valida evidencia real. La IA no debe autocorregirse con datos no verificados, porque eso amplifica errores.

