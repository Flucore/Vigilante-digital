# Plan de Pruebas — Maqueta Vigilante Digital

## Objetivo

Validar una demo funcional con cámaras IP/webcam capaz de:

1. Detectar una caída.
2. Detectar ingreso de persona con polera roja por al menos 1 segundo.
3. Detectar cambio de color de una luz tipo semáforo.
4. Activar triggers: correo, WhatsApp/webhook y bocina.
5. Guardar evidencia: snapshot, evento JSON y PDF.

## Ambiente de Prueba

- PC gamer con GPU Nvidia.
- Python 3.10+.
- 2 celulares Android con IP Webcam o webcams USB.
- Misma red WiFi para PC y celulares.
- Iluminación estable.
- Fondo limpio para la prueba de caída.

## Prueba 0 — Instalación

Comandos:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"
```

Criterio de éxito:

- `torch.cuda.is_available()` retorna `True` si hay GPU.
- Si retorna `False`, el sistema debe seguir funcionando en CPU/MediaPipe.

## Prueba 1 — Detectores sintéticos

Comando:

```powershell
pytest tests/test_color_detectors.py
```

Criterio de éxito:

- `test_red_shirt_detector_triggers_after_presence_window` pasa.
- `test_traffic_light_detector_reports_color_change` pasa.

## Prueba 2 — Cámaras IP conectadas

1. Abrir IP Webcam en cada celular.
2. Configurar URLs en `demo_config.json`.
3. Ejecutar:

```powershell
python scripts/demo_2cam.py
```

Criterio de éxito:

- Se ve vista dividida.
- HUD muestra FPS y estado.
- No aparece `SIN SEÑAL` por más de 5 segundos.

## Prueba 3 — Caída

Configuración:

```json
"module": "fall_detection"
```

Procedimiento:

1. Persona de pie frente a CAM_1.
2. Persona simula caída controlada sobre colchoneta.
3. Mantener postura horizontal por 1-2 segundos.

Criterios:

- Estado cambia a `ALERTA`.
- Se guarda snapshot en `test_outputs/snapshots`.
- Se registra evento en `outputs/events_CAM_1.json`.
- Tecla `p` genera PDF.

## Prueba 4 — Polera Roja por 1 Segundo

Configuración:

```json
"module": "red_shirt",
"min_presence_sec": 1.0,
"min_area_ratio": 0.025
```

Procedimiento:

1. Persona con polera roja entra al cuadro.
2. Mantenerse visible por al menos 1 segundo.
3. Repetir con polera no roja.

Criterios:

- Con polera roja: evento `red_shirt_entry`.
- Sin polera roja: no dispara evento.
- El evento incluye `red_area_ratio`.

## Prueba 5 — Cambio de Luz/Semáforo

Configuración:

```json
"module": "traffic_light",
"roi": [450, 120, 360, 360]
```

Procedimiento:

1. Apuntar cámara a luz o pantalla con círculo rojo.
2. Cambiar a verde.
3. Cambiar a amarillo.

Criterios:

- Evento `traffic_light_change`.
- Metadata contiene `previous_color` y `current_color`.
- Cambio se detecta solo tras estabilidad mínima.

## Prueba 6 — Triggers

Configurar:

```json
"triggers": {
  "enabled": true,
  "default_routes": ["speaker"],
  "routes_by_event": {
    "fall": ["speaker", "whatsapp", "email"]
  }
}
```

Criterios:

- Bocina recibe POST o reproduce URL.
- WhatsApp webhook recibe payload.
- Email se envía solo si hay PDF y credenciales Gmail.

## Métricas a Registrar

- FPS promedio por cámara.
- Latencia evento: tiempo desde acción hasta alerta.
- Falsos positivos por 10 minutos.
- Falsos negativos por 10 intentos.
- Tiempo de generación PDF.
- Tiempo de entrega de WhatsApp/email.

## Resultado Esperado para Demo Ejecutiva

- Caída: alerta en menos de 2 segundos.
- Polera roja: alerta tras 1 segundo de presencia.
- Semáforo: cambio reconocido en menos de 1 segundo.
- PDF generado manualmente con `p`.
- Sistema sigue funcionando aunque Firebase, email o WhatsApp estén desactivados.

