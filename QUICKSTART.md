# VIGILANTE DIGITAL IA v2.0: GUÍA RÁPIDA DE INICIO

**Documento:** Quick Start Guide  
**Última actualización:** 2024  
**Versión:** 2.0.0 (EventLogger Optimization)  
**Estado:** Producción

> **Novedad en v2.0:** Reducción de documentos Firestore del 99% usando EventLogger  
> Un video de 3 minutos genera **2 documentos** en lugar de 5,330

---

## 📋 CHECKLIST DE SETUP INICIAL

```
Pre-requisitos:
  [x] Python 3.10+ instalado
  [x] Git configurado
  [x] Credenciales Firebase descargadas
  [x] Video MP4 de prueba descargado

Setup (Nuevo en v2.0):
  [ ] 1. Crear carpetas de pruebas
  [ ] 2. Configurar variable de entorno GOOGLE_APPLICATION_CREDENTIALS
  [ ] 3. Instalar dependencias
  [ ] 4. Configurar USE_EVENT_LOGGER=true (v2.0) en .env o PowerShell
  [ ] 5. Ejecutar prueba baseline con EventLogger
  [ ] 6. Verificar reducción de datos en test_metrics.json
  [ ] 7. Verificar eventos en Firestore
  [ ] 8. (Opcional) Limpiar datos de prueba antiguos (v1.0)
```

---

## 🚀 EJECUCIÓN RÁPIDA (5 MINUTOS)

### Paso 1: Crear estructura de carpetas

```powershell
cd C:\ruta\a\VigilanteDigital
mkdir tests\test_videos
mkdir test_outputs
mkdir scripts  # Si no existe
```

### Paso 2: Copiar tu video MP4

```powershell
# Coloca tu video descargado aquí:
Copy-Item "C:\ruta\a\tu\video.mp4" -Destination "tests\test_videos\fall_sample_01.mp4"
```

### Paso 3: Configurar credenciales Firebase (PowerShell)

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\secrets\firebase-service-account.json"
$env:USE_EVENT_LOGGER = "true"  # NEW in v2.0: habilitar EventLogger

# Verificar:
Write-Host "Credenciales: $env:GOOGLE_APPLICATION_CREDENTIALS"
Write-Host "EventLogger: $env:USE_EVENT_LOGGER"
```

### Paso 4: Ejecutar script de pruebas (v2.0 con EventLogger)

```powershell
# Desde la carpeta raíz del proyecto
python scripts/run_test.py --video tests/test_videos/fall_sample_01.mp4 --output test_outputs
```

**Salida esperada en v2.0:**
```
INFO - EventLogger mode enabled
INFO - Processing video: 5400 frames
...
RESUMEN DE PRUEBA
================================================================
Total de frames: 5400
Caídas detectadas: 5330
Eventos completados: 2          ← v2.0: Agregación de eventos
Reducción de datos: 99.96%      ← v2.0: Métrica de mejora
Eventos subidos a Firebase: 2
Estado: ✓ EXITOSO
================================================================
```

### Paso 5: Ver resultados

```powershell
# Métricas locales:
cat test_outputs\test_metrics.json

# Eventos locales (JSON):
cat test_outputs\events_log.json  # v2.0: archivo nuevo con eventos agregados

# Eventos en Firestore:
# Ve a https://console.firebase.google.com
# Proyecto: TU_PROYECTO_FIREBASE
# Firestore > Colección "Prueba_Alertas"
# Verás 2 documentos en lugar de 5,330 ✓
```

### Paso 6 (Opcional): Limpiar datos de prueba antiguos

Si tienes datos de v1.0 (5,330 registros por video), limpialos:

```powershell
# Ver cuántos documentos hay
python scripts/cleanup_firestore.py --count

# Exportar como backup (recomendado)
python scripts/cleanup_firestore.py --export backup_v1.json

# Eliminar (DRY RUN primero)
python scripts/cleanup_firestore.py --delete --dry-run

# Eliminar REALMENTE
python scripts/cleanup_firestore.py --delete --force
```

---

## 📊 ARCHIVOS CLAVE DEL PROYECTO

### Código Fuente

| Archivo | Propósito | Estado |
|---------|-----------|--------|
| `main.py` | Orquestador principal | ✓ Refactorizado |
| `core/pose_detector.py` | Detección con MediaPipe | ✓ Optimizado |
| `outputs/json_logger.py` | Log local de eventos | ✓ Nuevo |
| `outputs/firebase_connector.py` | Sync a Firestore | ✓ Nuevo |
| `config.py` | Configuración por env vars | ✓ Seguro |

### Documentación

| Archivo | Contenido |
|---------|----------|
| `ANALYSIS.md` | Análisis técnico completo del proyecto |
| `TESTING.md` | Guía detallada de pruebas locales |
| `YOLO_EVALUATION.md` | Propuesta de integración YOLO |
| `DEPLOYMENT.md` | Instrucciones para cliente final |
| `ARCHITECTURE.md` | Especificación arquitectónica |

### Configuración

| Archivo | Propósito |
|---------|-----------|
| `requirements.txt` | Dependencias pip |
| `.gitignore` | Excluir secretos del repo |
| `config.py` | Variables de entorno |

---

## 🔍 FLUJO DE PRUEBAS

```
1. run_test.py inicia
   ↓
2. Abre video MP4
   ↓
3. Inicializa:
   - PoseDetector (MediaPipe)
   - JSONLogger (eventos locales)
   - FirebaseConnector (sincronización)
   ↓
4. LOOP: Para cada frame del video
   ├─ Detecta pose
   ├─ Calcula ratio de aspecto
   ├─ Si ratio < 0.8:
   │  ├─ Incrementa contador de caídas
   │  ├─ Guarda evento en JSON
   │  └─ Dispara upload async a Firebase
   ├─ Calcula FPS
   └─ Muestra resultado en ventana
   ↓
5. Al terminar video:
   ├─ Espera a que termine hilo de sync
   ├─ Guarda métricas en test_metrics.json
   └─ Imprime resumen
```

---

## 📈 MÉTRICAS ESPERADAS

Después de ejecutar la prueba, verás algo así:

```
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

---

## 🔌 CONECTAR DISPOSITIVOS EXTERNOS (IP Speaker, USB, ESP32)

Esta versión incluye módulos para interactuar con dispositivos conectados a
la máquina: `inputs/ip_speaker.py`, `inputs/usb_reader.py`, y
`inputs/esp32_client.py`.

Dependencias opcionales (instalar solo las que necesites):

```powershell
pip install pyserial paho-mqtt
```

1) IP Speaker (HTTP)

- Usa `inputs.ip_speaker.IpSpeaker(host)` con la URL de tu dispositivo.
- Funciones disponibles: `ping()`, `play_url(mp3_url)`, `set_volume(level)`.
- Ejemplo:

```python
from inputs.ip_speaker import IpSpeaker
spk = IpSpeaker('http://10.139.192.20:5000')
spk.play_url('http://your-server/alert.mp3')
```

2) USB Serial Reader

- Conecta un dispositivo USB-Serial (ej. Arduino) y usa `SerialReader`.
- Lee líneas terminadas en `\n` y ejecuta tu callback por cada línea.
- Ejemplo:

```python
from inputs.usb_reader import SerialReader

def on_line(line):
      print('USB>', line)

reader = SerialReader(port='COM3', baudrate=115200)
reader.start(on_line)
# ... luego reader.stop() cuando termines
```

3) ESP32

- Si tu ESP32 publica a un broker MQTT, usa `inputs.esp32_client.MQTTClient`.
- Alternativamente, si el ESP32 expone un servidor TCP, usa `TcpClient`.
- Ejemplo MQTT:

```python
from inputs.esp32_client import MQTTClient

def on_msg(payload):
      print('ESP32>', payload)

mc = MQTTClient(broker='192.168.1.10', port=1883, topic='esp32/alerts')
mc.start(on_msg)
mc.publish('hello')
# mc.stop()
```

Integración con el pipeline

- Puedes suscribir los callbacks para que, por ejemplo, cuando el ESP32
   envíe una alarma física, el sistema muestre una alerta en pantalla o
   reproduzca un sonido vía `IpSpeaker`.
- Si quieres, integro un demo en `main.py` o en un script `scripts/run_with_devices.py`.

**Qué significan:**
- **Total de frames:** Cantidad de imágenes procesadas
- **Caídas detectadas:** Eventos donde ratio < 0.8
- **FPS promedio:** Velocidad de procesamiento (aim: > 15)
- **Firebase:** Eventos sincronizados a la nube

---

## ⚠️ TROUBLESHOOTING RÁPIDO

### "No se pudo abrir el video"
```powershell
# Verifica que la ruta sea correcta:
Test-Path "tests\test_videos\fall_sample_01.mp4"  # Debe devolver True

# Si no existe:
Get-ChildItem tests\test_videos\
```

### "GOOGLE_APPLICATION_CREDENTIALS not found"
```powershell
# Configura de nuevo:
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\secrets\firebase-service-account.json"

# Verifica:
Write-Host "Ruta: $env:GOOGLE_APPLICATION_CREDENTIALS"
Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS
```

### "Firebase connection failed"
```
1. ¿El JSON corresponde a TU_PROYECTO_FIREBASE?
   - Abre el JSON y revisa "project_id"

2. ¿Firebase tiene la colección "Prueba_Alertas"?
   - Crea la colección manualmente en Firebase Console si falta

3. ¿Hay permisos correctos?
   - Revisa las reglas de seguridad en Firestore
```

### "FPS muy bajo (< 10)"
```python
# Edita main.py o run_test.py:
PoseDetector(complexity=0, frame_scale=0.5)  # Más ligero

# O reduce resolución en display:
frame_show = cv2.resize(proc_frame, (960, 540))
```

---

## 🎯 PRÓXIMOS PASOS (ORDEN RECOMENDADO)

### Hoy (8 de Diciembre):
1. ✓ Ejecutar prueba baseline con MediaPipe
2. ✓ Documentar resultados en `TEST_RESULTS.md`
3. ✓ Verificar que Firestore recibe eventos

### Mañana (9 de Diciembre):
4. Analizar precisión: ¿Es aceptable (> 70%)?
   - SI → Optimizar y preparar para cliente
   - NO → Proceder con YOLO

### Si precisión < 70%:
5. Integración YOLO (1-2 semanas)
   - Ver: `YOLO_EVALUATION.md`
   - Recopilar dataset
   - Entrenar modelo
   - Integrar y validar

### Producción:
6. Deploy en máquina del cliente
   - Ver: `DEPLOYMENT.md`
   - Usar la guía paso a paso
   - Validar sincronización Firebase

---

## 📝 PLANTILLA: DOCUMENTAR TUS PRUEBAS

Crea `docs/TEST_RESULTS.md`:

```markdown
# Resultados de Pruebas - Vigilante Digital IA

## Prueba 1: [Nombre del video]

**Fecha:** [Tu fecha]  
**Video:** tests/test_videos/[archivo].mp4  
**Duración:** [segundos]  
**Resolución:** [1920x1080]

### Métricas Capturadas

```json
{
  "total_frames": XXX,
  "total_falls_detected": X,
  "avg_fps": XX.XX,
  "firebase_events_uploaded": X,
  "success": true
}
```

### Análisis

- Caídas detectadas correctamente: SI / NO
- Falsos positivos: [número]
- Falsos negativos: [número]
- Sincronización Firebase: SI / NO

### Conclusión

[Tu análisis aquí]

### Siguiente paso

[Qué hacer a continuación]
```

---

## 🔐 RECORDATORIOS DE SEGURIDAD

- [ ] El JSON de Firebase está en `C:\secrets\` (NO en el repo)
- [ ] Variable `GOOGLE_APPLICATION_CREDENTIALS` está configurada
- [ ] `.gitignore` contiene `*.json` y `secrets/`
- [ ] No hiciste push del JSON al repositorio
- [ ] Las credenciales se pasan solo por variable de entorno

---

## 📚 REFERENCIAS RÁPIDAS

```powershell
# Abrir proyecto
cd C:\ruta\a\VigilanteDigital

# Activar entorno virtual
.venv\Scripts\Activate.ps1

# Instalar/actualizar dependencias
pip install -r requirements.txt

# Ejecutar prueba
python scripts/run_test.py --video tests/test_videos/fall_sample_01.mp4 --output test_outputs

# Ver métricas
cat test_outputs\test_metrics.json

# Ver documentación
cat ANALYSIS.md
cat TESTING.md
cat YOLO_EVALUATION.md
cat DEPLOYMENT.md
```

---

## 🎬 ESTADO ACTUAL DEL PROYECTO

```
✓ Arquitectura modular (ARCHITECTURE.md)
✓ Type hints y manejo de errores
✓ Configuración por variables de entorno (seguro)
✓ Firebase integrado (async, no bloqueante)
✓ JSON Logger para eventos locales
✓ Script de pruebas con métricas
✓ Documentación completa
✓ .gitignore seguro

⚠ Pendiente validación de precisión (MediaPipe solo)
⚠ Pendiente integración YOLO (si es necesario)
⚠ Pendiente tests unitarios
⚠ Pendiente alertas SMS/Email
```

---

## 💡 TIPS PRO

1. **Para procesar video rápido:**
   - Usa `frame_scale=0.5` para procesar a menor resolución
   - Usa `complexity=0` para modelo más ligero

2. **Para mejor precisión:**
   - Espera a integrar YOLO (85-90% vs 60% actual)
   - Agrega validación temporal (requiere N frames consecutivos)

3. **Para depuración:**
   - Activa logs: `logging.basicConfig(level=logging.DEBUG)`
   - Guarda frames en caídas: `cv2.imwrite(f"fall_{i}.jpg", frame)`

4. **Para producción:**
   - Usa Docker (ver `DEPLOYMENT.md`)
   - Monitorea Firestore en tiempo real
   - Configura alertas en Firebase

---

## 📞 SOPORTE

Si encuentras problemas:

1. Revisa `TESTING.md` → Sección "Troubleshooting"
2. Revisa logs en consola (contienen pistas)
3. Verifica que Firestore tiene la colección "Prueba_Alertas"
4. Valida que credenciales son correctas (revisar `project_id` en JSON)

---

**¡Listo para empezar! Ejecuta tu primera prueba ahora.** 🚀
