# README — Demo Ejecutivo Vigilante Digital IA

**Para presentación a empresa de seguridad — PC gamer con GPU**

---

## Preparación (el día anterior)

### 1. Instalar dependencias

```powershell
cd c:\Users\Valen\Documents\VigilanteDigital_1.0

# PyTorch con GPU (hacer esto PRIMERO)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Resto de dependencias
pip install -r requirements.txt
```

### 2. Verificar GPU

```powershell
python -c "import torch; print('GPU OK:', torch.cuda.get_device_name(0))"
# Debe mostrar: GPU OK: NVIDIA GeForce RTX XXXX
```

### 3. Descargar modelo YOLOv8

El modelo se descarga automáticamente la primera vez. Para pre-descargarlo:

```powershell
python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"
# Descarga ~6MB, solo una vez
```

---

## Setup el día de la presentación

### Paso 1 — Configurar la red WiFi

Conectar a la misma red WiFi:
- PC gamer (donde corre el demo)
- Celular 1 (Cámara zona de trabajo)
- Celular 2 (Cámara control de acceso)

### Paso 2 — Instalar IP Webcam en los celulares

1. Instalar **IP Webcam** de Pavel Khlebovich (gratuita, Play Store)
2. Abrir la app en cada celular
3. Ir al fondo de la pantalla → presionar **"Start server"**
4. Anotar la URL que aparece en pantalla (ej: `http://192.168.1.101:8080`)

### Paso 3 — Configurar las URLs en demo_config.json

Editar el archivo `demo_config.json`:

```json
"cameras": [
  {
    "id": "CAM_1",
    "name": "Zona de Trabajo",
    "url": "http://192.168.1.101:8080/video",   ← IP del celular 1
    ...
  },
  {
    "id": "CAM_2", 
    "name": "Control de Acceso",
    "url": "http://192.168.1.102:8080/video",   ← IP del celular 2
    ...
  }
]
```

**Atajo**: también puedes pasar las IPs directamente al .bat:
```
start_demo.bat 192.168.1.101 192.168.1.102
```

### Paso 4 — Probar las URLs antes de la presentación

Abrir en el navegador del PC:
- `http://192.168.1.101:8080/video` → debe mostrar video
- `http://192.168.1.102:8080/video` → debe mostrar video

Si no carga: verificar que estén en la misma red WiFi.

### Paso 5 — Iniciar el demo

```powershell
# Doble-clic en start_demo.bat
# O desde PowerShell:
python scripts/demo_2cam.py
```

---

## Durante la presentación

### Ventana principal

- **Vista dividida**: CAM_1 (izquierda) | CAM_2 (derecha)
- **Barra superior**: nombre cámara, zona, FPS, timestamp
- **Estado**: NORMAL (verde) / ALERTA (rojo parpadeante) / INTRUSIÓN (rojo)
- **Barra inferior**: motor de IA activo, contador de eventos

### Teclas del demo

| Tecla | Acción |
|-------|--------|
| `q` o ESC | Salir del demo |
| `ESPACIO` | Pausar / Reanudar |
| `p` | Generar PDF del último evento |
| `s` | Screenshot manual (guarda en test_outputs/) |
| `r` | Resetear alertas visuales |
| `f` | Pantalla completa / ventana |

### Guion de la demo en vivo

**Minutos 1-2:** Mostrar la pantalla con las 2 cámaras activas. Explicar:
> "Esto es el Vigilante Digital. Dos cámaras, detección en tiempo real, 40 FPS con GPU."

**Minuto 3:** Alguien se acerca a la CAM_2 y cruza la línea naranja.
> "La línea define el perímetro. Al cruzarla, alerta inmediata. La zona queda registrada."

**Minuto 4:** Alguien se tira al piso frente a la CAM_1.
> "Detección de caída. El sistema identifica en menos de 1 segundo y registra el evento."

**Minuto 5:** Presionar `p` para mostrar el PDF generado automáticamente.
> "Este reporte queda en el sistema. Timestamp, foto, duración. Cadena de custodia lista."

**Minuto 6-7:** Mostrar que funciona con cualquier cámara IP, sin hardware propietario.
> "Funciona con celulares Android, cámaras Hikvision, Dahua, cualquier stream RTSP."

---

## Solución de problemas frecuentes

### "SIN SEÑAL" en las cámaras

1. Verificar que IP Webcam está corriendo en el celular
2. Verificar que el celular y el PC están en la misma red
3. Probar la URL en el navegador del PC
4. Reiniciar el server en la app IP Webcam

### El demo corre lento (menos de 15 FPS)

- Verificar GPU: `python -c "import torch; print(torch.cuda.is_available())"`
- Si muestra `False`: instalar drivers NVIDIA + CUDA 12.1
- Bajar resolución en IP Webcam a 480p temporalmente

### "ultralytics no disponible"

```powershell
pip install ultralytics
# Si falla: pip install ultralytics --no-cache-dir
```

### Error al generar PDF

```powershell
pip install reportlab pillow
```

---

## Archivos generados durante el demo

```
test_outputs/
├── snapshots/
│   ├── CAM_1_fall_20260427_120530.jpg     ← foto del evento de caída
│   └── CAM_2_perimeter_20260427_120612.jpg
├── reporte_fall_20260427_120530.pdf        ← PDF generado con 'p'
└── screenshot_manual_20260427_120545.jpg   ← captura con 's'

outputs/
├── events_CAM_1.json    ← log de eventos cámara 1
└── events_CAM_2.json    ← log de eventos cámara 2
```

---

## Configuración recomendada de IP Webcam

En la app IP Webcam, ajustar:
- **Resolución de video**: 1280x720 (720p)
- **FPS**: 25-30
- **Calidad**: 60-70 (balance velocidad/imagen)
- **Orientación**: Landscape (horizontal)
- **Focus**: activar "Continuous focus"

---

*Vigilante Digital IA v2.5 — Demo listo para presentación ejecutiva*
