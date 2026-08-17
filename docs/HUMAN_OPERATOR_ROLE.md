# Rol del humano — supervisor de aprendizaje

| Campo | Valor |
|---|---|
| Estado | Vigente (elevado Unidad 3 · 2026-08-16) |
| Canónico | [REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md](REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md) · [04_VISION_COMERCIAL…](REFORMULACION/04_VISION_COMERCIAL_Y_VENTAS.md) |

## Rol general

El humano **no compite** con la IA.  
El humano **calibra (M0), audita (curiosidad/alertas), enseña (M2), confirma conducta (M3) y autoriza promote**.  
La IA es hipótesis versionada; el humano es fuente de verdad.

## Mapa de responsabilidades

| Función | Memoria / loop | Quién típico |
|---|---|---|
| Calibrar zonas (piscina, muro, gallinero) | M0 | Instalador / operador |
| Revisar alertas y FAR percibido | Alertas | Operador seguridad / cliente |
| Auditar cola de curiosidad | HITL | Revisor HITL |
| Marcar FN (“debió alertar”) | Curiosidad | Operador |
| Subir álbum de producto + validar máscaras | M2 | Cliente admin + revisor |
| Distinguir “falla de cámara” vs “falla de modelo” | M0 vs train | Revisor |
| Autorizar promote / rollback | ModelCard | Fundador FluCore (piloto) / rol contractual |
| Cumplimiento (cartelería, consentimiento) | Legal | Cliente + FluCore en contrato |

`reviewer_id` debe quedar en cada decisión HITL (cadena de custodia).

## Antes del demo / piloto

- Iluminación, ángulo, red, URLs de config.  
- Calibrar ROI / `perimeter_line` / (futuro) máscaras M0.  
- Probar ≥ 30 min antes de mostrar a cliente.  
- Confirmar que Firebase no es requisito del relato.

## Durante el demo

### Operador técnico

- Arrancar runner/demo; vista estable; teclas `p` PDF, `s` screenshot, etc. según script vigente.

### Actor de prueba

- Caída segura; cruce de perímetro controlado; no improvisar “niño en piscina” con menores reales en grabación sensible sin protocolo.

### Narrador comercial

Debe decir:

- No reemplazamos al guardia: lo multiplicamos con criterio de **este** sitio.  
- Detectamos eventos y dejamos evidencia; no solo grabamos.  
- Aprendemos con supervisión humana — no “solo”.  
- M0 (borde irregular) es ventaja frente a línea recta de cámara con IA.

## Después: validación y aprendizaje

1. Revisar snapshots/PDF.  
2. Clasificar: acierto / FP / FN / problema de cámara / zona mal calibrada.  
3. FP de cámara → recalibrar M0, **no** meter a train.  
4. FN → CuriositySample de máximo valor.  
5. Etiquetar con `scripts/add_dataset_image.py` (flujo actual) hasta existir dashboard HITL.  
6. Nunca pedir “suban 300 fotos y que se actualice solo el edge”.

## Decisión de mejora (árbol)

Para cada error:

1. ¿Cámara / iluminación / ángulo? → hardware u operación.  
2. ¿Zona/ROI mal calibrada? → M0.  
3. ¿Regla temporal / IoU? → M3 config.  
4. ¿Clase gruesa falló? → revisar M1 (raro).  
5. ¿Subclase del cliente? → M2 + domain mix.  
6. ¿Solo entonces train? → hub + gold-set + shadow/canary.

## Principio de trabajo

El humano es el **supervisor de aprendizaje**.  
La maqueta y el piloto deben generar evidencia suficiente para mejorar el sitio **sin** exponer datos innecesarios ni romper Ley 21.663 / políticas FluCore.
