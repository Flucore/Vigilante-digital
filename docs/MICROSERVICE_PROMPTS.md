# Prompts para Avanzar por Microservicios

Usar estos prompts paso a paso para evolucionar Vigilante Digital desde maqueta local a plataforma escalable.

---

## 1. Event Bus

```text
Actúa como arquitecto backend senior. En este proyecto VigilanteDigital, diseña e implementa un microservicio `event-bus` local en Python/FastAPI que reciba eventos canónicos desde `scripts/demo_2cam.py`, los valide con Pydantic, los guarde en SQLite/Postgres y los publique a subscribers internos. Mantén compatibilidad con el formato de evento definido en `.cursor/rules/04-outputs-eventos.mdc`. Incluye README, pruebas y ejemplo de curl.
```

## 2. Notification Service

```text
Implementa un microservicio `notification-service` en Python/FastAPI para enviar alertas por email, WhatsApp webhook/Twilio y bocina IP. Debe recibir eventos desde el event-bus, aplicar reglas por `event_type`, reintentar con backoff, registrar auditoría y nunca bloquear el pipeline de visión. Usa configuración por variables de entorno y un archivo `notification_config.json`.
```

## 3. Report Service

```text
Extrae la generación de PDF actual a un microservicio `report-service`. Debe recibir un evento JSON y una ruta/URL de snapshot, generar PDF con ReportLab, almacenar el resultado y devolver la ruta. Debe soportar plantillas por cliente, logo y campos de compliance. Incluye tests con eventos falsos.
```

## 4. Camera Agent

```text
Convierte `scripts/demo_2cam.py` en un `camera-agent` reusable. Cada agente lee una cámara IP/RTSP, corre un módulo de detección configurado, produce eventos canónicos y los envía al event-bus. Debe soportar reconexión, métricas FPS, healthcheck y configuración por JSON.
```

## 5. Vision Inference Service

```text
Diseña un `vision-inference-service` con GPU que reciba frames o snapshots desde camera-agents y ejecute modelos YOLOv8-pose, YOLOv8-seg y detectores custom. Debe exponer endpoints `/infer/fall`, `/infer/object`, `/infer/segment`, manejar batching y devolver resultados normalizados.
```

## 6. Dataset Service

```text
Implementa un `dataset-service` para aprendizaje human-in-the-loop. Debe permitir cargar imágenes, asignar etiquetas, registrar reviewer, guardar manifest.jsonl y exportar datasets en formato YOLO. Usa como base `core/learning_dataset.py`. Incluye CLI para agregar imágenes desde `test_outputs/snapshots`.
```

## 7. Human Review Dashboard

```text
Crea un dashboard web minimalista para revisión humana de eventos. Debe listar eventos, mostrar snapshot, permitir marcar `correcto`, `falso_positivo`, `falso_negativo`, asignar etiqueta y enviar imagen al dataset-service. Debe ser simple para operar durante pilotos.
```

## 8. Training Pipeline

```text
Diseña un pipeline de entrenamiento para modelos YOLOv8 custom. Debe tomar datasets exportados, dividir train/val/test, entrenar, registrar métricas, guardar versión del modelo y generar un reporte de precisión por clase. Debe priorizar reproducibilidad.
```

## 9. Thermal Integration

```text
Investiga e implementa una integración inicial para cámaras térmicas. Diseña una interfaz `ThermalFrame` y un detector `thermal_detector.py` que soporte umbrales de temperatura, blobs calientes/fríos y eventos `thermal_alert`. Documenta cámaras compatibles y supuestos de calibración.
```

## 10. VMS/CCTV Integration

```text
Agrega soporte robusto para cámaras RTSP/Hikvision/Dahua. Implementa reconexión, timeout, detección de frame congelado, caída de stream y métricas por cámara. Debe funcionar como fuente para `camera-agent`.
```

## 11. Compliance Automation

```text
Implementa utilidades de compliance: retención automática de snapshots/eventos, borrado seguro por fecha, logging de accesos, y generación de reporte de auditoría. Debe alinearse con `COMPLIANCE.md`, Ley 21.663, ISO 27001 e IEC 62676.
```

## 12. Product Demo Mode

```text
Mejora el modo demo ejecutivo: presets por escenario, simulador de eventos, pantalla de métricas, estado de triggers y botón para generar reporte. Mantén todo funcionando sin servicios externos para presentaciones offline.
```

