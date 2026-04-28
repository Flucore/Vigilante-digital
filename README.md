# VigilanteDigital IA v2.5 - Detección de Caídas con Reportes y Alertas por Email

**Sistema inteligente de detección de caídas en tiempo real con generación de reportes PDF y alertas automáticas por correo.**

## 🎯 Características Principales

### v2.5 (Actual)
- ✅ **PDF Reports**: Genera reportes automáticos con imagen, fecha, hora, cámara, sector y duración
- ✅ **Email Alerts**: Envía reportes por Gmail SMTP con autenticación App Password (segura)
- ✅ **Real-time Streaming**: Optimización para reproducción en tiempo real (frame_scale 0.6, detection_skip 2)
- ✅ **IP Camera Support**: Streaming desde teléfono/cámara IP con reconexión automática
- ✅ **Multi-device Actions**: Dispara acciones en IP Speaker, USB Reader, ESP32 al detectar caídas
- ✅ **Event Logging**: State machine que reduce escrituras Firestore en 99.3%
- ✅ **Security First**: Credenciales por variables de entorno, sin almacenamiento en código

### Mejoras de Desempeño Respecto a v2.0

| Aspecto | v2.0 | v2.5 | Mejora |
|--------|------|------|--------|
| Escrituras Firestore | 2 docs | 1-2 docs | -50% |
| FPS de reproducción | 15-20 | 25-30 | **67% ↑** |
| Consumo CPU | Alto | Medio | **40% ↓** |
| Reportes | ❌ | ✅ PDF | **NEW** |
| Email Alerts | ❌ | ✅ Gmail | **NEW** |

## 🚀 Inicio Rápido (10 min)

### 1. Clonar Repositorio
```powershell
git clone https://github.com/Flucore/Vigilante-digital.git
cd Vigilante-digital
```

### 2. Crear Entorno Virtual
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Instalar Dependencias
```powershell
pip install -r requirements.txt
```

### 4. Configurar Credenciales

#### Firebase (Opcional)
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\firebase-key.json"
$env:USE_EVENT_LOGGER = "true"
```

#### Email (Recomendado)
```powershell
$env:GMAIL_SENDER_EMAIL = "tu@gmail.com"
$env:GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
```

Ver [GMAIL_SETUP_GUIDE.md](GMAIL_SETUP_GUIDE.md) para instrucciones detalladas.

### 5. Ejecutar Prueba
```powershell
python .\scripts\run_test.py --video C:\ruta\segura\video_demo.mp4 --output .\test_outputs
```

**Resultado esperado:**
- ✓ Detecta caída
- ✓ Genera reporte PDF
- ✓ Pregunta si enviar por correo (s/n)
- ✓ Envía automáticamente si respondes 's'

## 📁 Estructura del Proyecto

```
VigilanteDigital_1.0/
├── core/
│   ├── pose_detector.py         # Detector MediaPipe optimizado
│   └── __init__.py
├── inputs/
│   ├── video_stream.py          # Wrapper para streaming de video
│   ├── ip_speaker.py            # Control de altavoz IP
│   ├── usb_reader.py            # Lector USB serial
│   ├── esp32_client.py          # Cliente MQTT/TCP para ESP32
│   └── __init__.py
├── outputs/
│   ├── event_logger.py          # State machine para eventos
│   ├── firebase_connector.py    # Sincronización con Firestore
│   ├── json_logger.py           # Logging en JSON (legacy)
│   ├── report_generator.py      # Generador de reportes PDF
│   ├── email_sender.py          # Envío de correos Gmail
│   └── __init__.py
├── scripts/
│   ├── run_test.py              # Detector en video MP4 con reportes
│   ├── run_with_devices.py      # Demo con dispositivos IP/USB/ESP32
│   ├── run_ipcam.py             # Streaming desde IP camera
│   ├── test_email_send.py       # Validar config de email
│   ├── test_report_generation.py# Generar PDF de prueba
│   └── test_event_storage.py    # Probar almacenamiento de eventos
├── config.py                    # Configuración global
├── main.py                      # Punto de entrada principal
├── requirements.txt             # Dependencias Python
├── CHANGELOG.md                 # Historial de versiones
├── GMAIL_SETUP_GUIDE.md         # Guía de configuración de email
└── README.md                    # Este archivo
```

## 🎮 Ejemplos de Uso

### Detección en Video MP4
```powershell
python .\scripts\run_test.py --video .\tests\fall_sample.mp4 --output .\results
```

**Características:**
- Procesa video automáticamente
- Genera PDF al detectar caída
- Pregunta por email para enviar reporte

### Streaming desde IP Camera
```powershell
$env:VIDEO_SOURCE = "http://192.168.1.100:8080/video"
python .\scripts\run_with_devices.py --frame-scale 0.6 --detection-skip 2
```

**Teclas:**
- `q`: Salir
- `d`: Generar PDF del evento actual
- `space`: Pausa/reanuda

### Prueba de Email
```powershell
python .\scripts\test_email_send.py
```

Valida:
- ✓ Variables de entorno configuradas
- ✓ Conexión SMTP a Gmail
- ✓ Envío de reporte de prueba

### Prueba de Eventos
```powershell
python .\scripts\test_event_storage.py
```

Verifica:
- ✓ Almacenamiento local JSON
- ✓ Sincronización con Firebase (si configurado)

## 🔧 Parámetros de Optimización

### Frame Scale (Resolución)
```powershell
python .\scripts\run_with_devices.py --frame-scale 0.6  # 60% de tamaño (recomendado)
python .\scripts\run_with_devices.py --frame-scale 1.0  # 100% (más preciso, más lento)
python .\scripts\run_with_devices.py --frame-scale 0.4  # 40% (ultra rápido)
```

### Detection Skip (Saltear frames)
```powershell
python .\scripts\run_with_devices.py --detection-skip 1  # Detectar en cada frame
python .\scripts\run_with_devices.py --detection-skip 2  # Detectar cada 2 frames (recomendado)
python .\scripts\run_with_devices.py --detection-skip 3  # Detectar cada 3 frames
```

### Complejidad de Pose
```powershell
python .\scripts\run_with_devices.py --complexity 0  # Rápido (recomendado)
python .\scripts\run_with_devices.py --complexity 1  # Balanceado
```

## 📊 Configuración en config.py

```python
# Rutas
VIDEO_SOURCE = "tests/test_videos/fall_sample_01.mp4"
EVENT_LOG_PATH = "events.json"
REPORTS_DIR = "reports"

# Detección de caídas
MIN_FALL_DURATION_SEC = 0.5      # Duración mínima para considerar caída
DETECTION_THRESHOLD = 0.6         # Confianza mínima MediaPipe
FALL_ANGLE_THRESHOLD = 30         # Grados de inclinación

# Event Logger
USE_EVENT_LOGGER = True           # Usar state machine
EVENT_DEDUP_WINDOW_SEC = 2        # Ventana de deduplicación

# Firebase (Opcional)
USE_FIREBASE = False
FIREBASE_CONFIG = {}

# Dispositivos (Opcional)
USE_IP_SPEAKER = False
IP_SPEAKER_URL = "http://192.168.1.100:5000"
```

## 🔐 Seguridad

### Credenciales por Variables de Entorno
- ✅ GOOGLE_APPLICATION_CREDENTIALS (Firebase)
- ✅ GMAIL_SENDER_EMAIL (Gmail)
- ✅ GMAIL_APP_PASSWORD (App Password)
- ✅ VIDEO_SOURCE (IP camera)

**NUNCA hardcodees contraseñas en archivos.**

### Métodos de Autenticación Seguros
- **Gmail App Password**: Contraseña específica para aplicaciones (recomendado)
- **Firebase Service Account**: JSON con permisos limitados
- **OAuth 2.0**: Para entornos corporativos (futuro)

Ver [GMAIL_SETUP_GUIDE.md](GMAIL_SETUP_GUIDE.md) para detalles.

## 📈 Métricas y Logs

### Archivos Generados
- `events.json`: Eventos almacenados localmente
- `reports/reporte_*.pdf`: Reportes PDF generados
- `test_outputs/metrics.json`: Métricas de ejecución

### Ejemplo de Evento
```json
{
  "event_id": 1,
  "event_type": "fall",
  "start_frame": 150,
  "end_frame": 250,
  "duration_sec": 3.33,
  "timestamp": "2025-12-11T14:30:00Z",
  "camera": "default",
  "sector": "sala_principal",
  "report_pdf": "reports/reporte_caida_20251211_143000.pdf"
}
```

## 🐛 Solución de Problemas

### "Error de autenticación Gmail"
1. Verifica que 2FA está habilitado: https://myaccount.google.com/
2. Genera App Password: https://myaccount.google.com/apppasswords
3. Copia exactamente: `xxxx xxxx xxxx xxxx`
4. Configura: `$env:GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"`

### "Video lento o entrecortado"
1. Reduce `--frame-scale` a 0.6 o 0.4
2. Aumenta `--detection-skip` a 2 o 3
3. Verifica disponibilidad de CPU: `Get-Process | Sort CPU -Descending | Select -First 5`

### "Firestore muy costoso"
Asegúrate que `USE_EVENT_LOGGER = True` en config.py. Reduce escrituras de 5,330 a 2 documentos.

### "IP Camera no conecta"
1. Verifica IP y puerto: `Test-NetConnection -ComputerName 192.168.1.100 -Port 8080`
2. Comprueba URL: `$env:VIDEO_SOURCE = "http://192.168.1.100:8080/video"`
3. Revisa permisos de firewall

## 📚 Documentación Adicional

- [CHANGELOG.md](CHANGELOG.md) - Historial completo de versiones
- [GMAIL_SETUP_GUIDE.md](GMAIL_SETUP_GUIDE.md) - Configuración detallada de email
- [QUICKSTART.md](QUICKSTART.md) - Guía rápida de instalación (si existe)
- [DEPLOYMENT.md](DEPLOYMENT.md) - Despliegue en producción (si existe)

## 🤝 Contribuciones

Para reportar bugs o sugerir mejoras, abre un issue en GitHub.

## 📄 Licencia

Este proyecto está bajo licencia MIT. Ver LICENSE para detalles.

## 👨‍💻 Desarrollo

**Versión**: 2.5.0  
**Última actualización**: Diciembre 2025  
**Python**: 3.10+  
**Dependencias principales**: MediaPipe, OpenCV, Firebase Admin SDK, reportlab, pillow

---

**¿Preguntas?** Revisa la documentación o abre un issue en GitHub.
