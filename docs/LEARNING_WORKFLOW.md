# Flujo de Aprendizaje Human-in-the-Loop

| Campo | Valor |
|---|---|
| Estado | Vigente (elevado Unidad 3 · 2026-08-16) |
| Canónico de arquitectura | [REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md](REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md) |
| Glosario | [REFORMULACION/03_GLOSARIO.md](REFORMULACION/03_GLOSARIO.md) |

## Principio (inamovible)

El sistema aprende cuando el **humano** valida evidencia real.  
**La IA no se autocorrije** con datos no verificados.  
**Calibrar ≠ Entrenar.** Un polígono de piscina no es un `.pt`.

## Contrato: cuatro memorias

| Memoria | Qué hace el humano | ¿Train? |
|---|---|---|
| **M0** Geométrica | Calibra zonas con SAM/asistente (piscina, muro, gallinero…) | No |
| **M1** Percepción | No “enseña” clases COCO en cada auditoría; reporta fallos sistemáticos | Solo si clase gruesa falla de verdad |
| **M2** Taxonomía | Valida subclases; sube álbum + crops del sitio (domain mix) | Clasificador fino / adapter |
| **M3** Conductual | Confirma o corrige eventos compuestos; marca FN | Reglas primero; secuencia después |

Detalle y promote: ver doc `05_…`.

## Loop objetivo (servicios lógicos)

```text
Inferencia edge (M1) + zonas (M0) + reglas (M3)
        ↓
  alertas  |  Motor de Curiosidad (no umbral único)
        ↓
  Dashboard HITL (reviewer_id)
        ↓
  Dataset versionado + Gold-set (nunca en train)
        ↓
  Train en hub → ModelCard → shadow → canary → promote / rollback
```

El edge **nunca** entrena. Open-vocab solo como siembra en hub.

## Flujo actual implementado (semilla)

Sigue válido como MVP de etiquetado manual:

```text
Evento / snapshot
  → humano revisa
  → scripts/add_dataset_image.py
  → datasets/vigilante/images/<label>
  → manifest.jsonl
```

```powershell
python scripts/add_dataset_image.py `
  --image test_outputs/snapshots/CAM_1_fall_20260428_010000.jpg `
  --label fall `
  --reviewer operator `
  --notes "demo controlada"
```

Módulo: `core/learning_dataset.py`.

## Etiquetas iniciales (operativas)

Caídas: `fall`, `normal`, `sitting`, `bending`, `lying_no_fall`, `ambiguous`  
Perímetro: `perimeter_breach`, `perimeter_normal`  
Color/luz (demo): `red_shirt`, `not_red_shirt`, `traffic_*`  
Aprendizaje rico (objetivo): además `falso_positivo`, `falso_negativo`, `nueva_clase`, `zona_mal_calibrada`

## Reglas de etiquetado

1. Solo imágenes claras; si hay duda → `ambiguous`.
2. Guardar FP y FN (FN = valor máximo: lo que el modelo no vio).
3. “Problema de cámara/iluminación” → calibración M0, **no** train.
4. Sin consentimiento/base legal: no cargar personas a dataset.
5. Cliente A no mezcla con cliente B.
6. Preferir recortes/máscaras sin rostro si el objetivo no es identidad.
7. Catálogo de producto **solo** junto a crops CCTV del sitio (domain gap).

## Prohibido documentar u operar como “listo”

- Auto-mejora sin HITL.
- “300 fotos → fine-tune → deploy a todas las cámaras”.
- Entrenar clase YOLO `ladron_saltando_muro` / `zorro_atacando`.
- SAM en inferencia 24/7 de cámara.

## Próximas etapas (orden = sprints A–D)

1. **A:** M0 + IoU (calibración), sin train.  
2. **B:** cola de curiosidad + HITL + manifiesto con máscara/motivo.  
3. **C:** export YOLO/cls + M2 domain mix + ModelCard.  
4. **D:** job de train + shadow/canary/rollback.

Script futuro (no implementar en ola DOCS): `scripts/export_yolo_dataset.py` con split y **exclusión explícita del gold-set**.
