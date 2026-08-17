# Estrategia de Segmentación

| Campo | Valor |
|---|---|
| Estado | Vigente (elevado Unidad 3 · 2026-08-16) |
| Canónico | [REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md](REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md) |

## Tesis

La detección por **bounding box** dice “hay algo aquí”.  
La **máscara** dice “estos píxeles son el objeto”.  
**No se abandona el bbox:** el stack es híbrido (velocidad + geometría + forense).

**Calibrar ≠ Entrenar.** Una máscara de piscina en config (M0) no es un modelo reentrenado.

## Capas de percepción (híbrido)

| Capa | Para qué | Ejemplo |
|---|---|---|
| BBox + pose | Velocidad, caída, trepada | Care & Fall, climb |
| Máscara de instancia (YOLO-seg) | Geometría exacta en edge | Pie ∩ borde piscina |
| SAM/SAM2 | Anotación y commissioning | Operador calibra M0 / etiqueta dataset |
| Semántica de escena (futuro) | Agua vs patio vs muro | Contexto de Aqua |
| Reglas espacial-temporales | Criterio (M3) | IoU + persistencia + after_hours |
| Clasificador fino (M2) | Taxonomía cliente | Cat vs Komatsu |

## SAM / SAM2 — reglas

| Sí | No |
|---|---|
| Backend de anotación y commissioning | Loop 24/7 de cámara |
| Un clic → polígono de piscina/muro (M0) | “El sistema entiende la piscina” sin detector+IoU |
| Acelerar dataset (máscaras) | Clasificar por sí mismo |
| SAM2 propagar N frames de video | Sustituir YOLOv8-seg en edge |

SAM **recorta píxeles**; no asigna clase de negocio.

## YOLOv8/v11-seg en edge (M1)

- Instancias: persona, vehículo, animal, excavator…  
- Geofencing: máscara ∩ `SiteZoneMask` (IoU + tiempo).  
- Forense: guardar bbox **y** polígono/RLE cuando esté disponible.  
- Degradación: si no hay ultralytics, bbox fallback (ya en `segmentation_detector`).

## Técnicas actuales de demo (conservar)

| Técnica | Uso | Límite |
|---|---|---|
| HSV + ROI | Polera roja, semáforo | Iluminación / mismos colores |
| Línea virtual | Perímetro demo | No es muro irregular (M0) |
| YOLOv8-pose | Caída | No reemplaza máscara de zona |

## Ruta por horizonte

| Horizonte | Segmentación |
|---|---|
| Demo / piloto inmediato | Pose + línea/ROI; HSV donde aporte |
| Comercial C1 (Aprendizaje-A) | M0 máscara zona + IoU con persona (bbox o seg) |
| Piloto 90 días | YOLO-seg persona/objeto + SAM solo en etiquetado |
| Académico C–D | Taxonomía M2 + promote; no “un YOLO para todo” |

## Criterio de selección (actualizado)

| Caso | Inicial | Objetivo |
|---|---|---|
| Caída | YOLO-pose | Pose + validación temporal (+ secuencia auditada) |
| Piscina | Polígono M0 + person ∩ zona | Máscara fina + IoU + persistencia |
| Muro / climb | Línea o zona_wall + pose | `intrusion_climb` (M3), no clase YOLO única |
| Flota | Detector excavator | M2 clasificador fino + flota_autorizada |
| Polera / luz | HSV + ROI | Persona-seg + clasificador atributo |
| Dataset | Manual + add_dataset_image | SAM assist + gold-set |

## Anti-patrones

- “Abandonamos los bounding boxes.”  
- “SAM corre en la cámara.”  
- Un solo YOLOv8-seg con 80 clases custom del cliente.  
- Fotos de catálogo sin crops CCTV → producción.
