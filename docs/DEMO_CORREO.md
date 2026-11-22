# Demo de aviso por correo — instalar, correr y modificar

Rama: `demo-correo-instalacion` (sale de `academico`). Escrito para Víctor.

El módulo detecta caídas en clips de video procesados como si vinieran de una cámara IP
y, por cada caída, envía un correo con la imagen del momento, la fecha y hora del
análisis, la ubicación y el reporte PDF. Tiene una página web para elegir qué clips analizar.

**No modifica** `runner.py`, `core/yolo_fall_detector.py`, `outputs/event_logger.py` ni `eval/`.
Se engancha a `runner.set_event_sink` (el mismo receptor que usa el panel). Las
incoherencias que encontramos en el camino están en [DEUDA_TECNICA_CORREO.md](DEUDA_TECNICA_CORREO.md).

---

## 1. Traer la rama

Desde la carpeta del repositorio que ya tienes clonado:

```powershell
git fetch origin
git checkout demo-correo-instalacion
git branch --show-current          # debe decir demo-correo-instalacion
```

## 2. Dependencias

Con tu `.venv` activado (el mismo del manual de instalación):

```powershell
pip install -r requirements-academico.txt
pip install -r requirements-demo-correo.txt
```

`requirements-demo-correo.txt` agrega solo lo del módulo: fastapi, `uvicorn[standard]`,
reportlab y lapx. **No instales `requirements.txt`**: trae `playsound`, que no compila en
Python 3.12, y `mediapipe`, que mete un OpenCV 4.11 encima del 4.10 fijado para el experimento.

Comprobación (deben pasar todas, 65 a la fecha):

```powershell
pytest -q
```

## 3. Credenciales de correo (`.env`)

Damián te mandó por interno el remitente, la clave de aplicación y los destinatarios.
**Nunca van en git**: `.env` está en `.gitignore`.

```powershell
copy .env.example .env
notepad .env
```

En la sección `Email` deja estas tres líneas con los datos reales (si las agregas al final
del archivo también sirve: gana la última aparición de cada variable):

```
SMTP_USER=cuenta.remitente@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENTS=destino1@gmail.com, destino2@gmail.com
```

`SMTP_PASSWORD` es una **contraseña de aplicación** de Gmail (16 letras), no la clave de la
cuenta. El módulo solo lee del `.env` las variables `SMTP_*`, `GMAIL_*` y `EMAIL_*`.

Probar el envío (manda un único correo de prueba y termina):

```powershell
python demo_camara_ip.py --probar-correo
```

Debe terminar con `Resultado: Correo enviado HH:MM:SS · 2 destinatarios`.
Si dice `SIMULADO`, la consola indica qué variable falta.

## 4. Videos propios (no están en git)

Los clips grabados por el equipo muestran personas reales y quedan fuera del repositorio
(`/data/*` está en `.gitignore`). Damián te los pasa por interno. Cópialos con estos
nombres exactos en `data\propios\originales\`:

| Clip | Archivo | Ubicación (va en el correo) | Esperado |
|---|---|---|---|
| 09 | `PXL_20261122_192037719.mp4` | Patio interior con hojas secas y palmera | Caída |
| 02 | `PXL_20261122_191334008~2.mp4` | Vereda de acceso frente a la reja | Normal |
| 12 | `PXL_20261122_200819022~2.mp4` | Balcón de acceso, vista cenital | Caída |
| 13 | `PXL_20261122_200853566~2.mp4` | Balcón de acceso, vista cenital | Normal |
| 05 | `PXL_20261122_191654353.mp4` | Pasillo exterior con reja y jardín | Caída |

```powershell
mkdir data\propios\originales
# copiar ahí los 5 .mp4
```

Si falta alguno, la página lo marca como "Falta el video" y no deja analizarlo.

## 5. Correr

### Interfaz de análisis (la de la presentación)

```powershell
python demo_analisis.py
```

Abre `http://127.0.0.1:8000/analisis/` en el navegador:

- **Analizar los clips**: procesa los 5 en orden como la cámara `CAM_IP_01` (~3–4 min en CPU).
- **Analizar** en cada tarjeta: uno solo.
- **Correo de prueba**: valida credenciales sin procesar video.
- El chip verde "Envío real → 2 destinatarios" confirma que leyó el `.env`.
  Amarillo = simulado (genera imagen y PDF, no envía).

Opciones: `--sin-envio` (ensayo), `--metodo pose`, `--no-abrir`, `--port 8001`.
El panel de operador de siempre sigue en `http://127.0.0.1:8000/operator/`.

Resultado esperado con los clips actuales (criterio bbox): 12 y 05 detectadas, 02 y 13 sin
alarma, **09 no detectada** (oclusión de la palmera; tampoco la detecta pose). Llegan 2 correos.

### Cámara IP con un video continuo

```powershell
python demo_camara_ip.py --esperar
```

Usa `data\demo\caidas_demo_30s.mp4`: 5 caídas de UR Fall en 34 s. Si no existe, lo arma solo
desde `data\goldset` con `scripts\armar_video_demo.py`. Llegan 5 correos.

### Detener

`Ctrl+C` en la terminal. Si el puerto 8000 queda ocupado:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id <OwningProcess> -Force
```

## 6. Dónde modificar

| Quiero cambiar… | Archivo | Qué tocar |
|---|---|---|
| Clips, su ubicación o el resultado esperado | `config_demo_correo.json` | sección `clips` (`id`, `archivo`, `ubicacion`, `esperado`) |
| Nombre de la cámara | `config_demo_correo.json` | `cameras[0].name` |
| Una caída = un correo (agrupación) | `config_demo_correo.json` | `correo.ventana_agrupacion_s` (3,0 s) |
| Ignorar fragmentos cortos | `config_demo_correo.json` | `correo.duracion_minima_s` (0,5 s) |
| Tope de correos por tanda | `config_demo_correo.json` | `correo.max_correos_por_sesion` (8) |
| Instalación y prefijo del asunto | `config_demo_correo.json` | `correo.instalacion`, `correo.asunto_prefijo` |
| Texto y diseño del correo | `outputs/notificador_correo.py` | `_datos`, `_asunto`, `_cuerpo`, `_cuerpo_html` |
| Imagen del correo (marco, franja) | `outputs/notificador_correo.py` | `_preparar_imagen`, `_marcar`, `_franja` |
| Página de análisis | `api/static/analisis.html` | HTML/CSS/JS en un solo archivo |
| Lógica de la tanda (orden, resultados) | `demo_analisis.py` | clase `Controlador` |
| Rutas HTTP de la página | `api/analisis_clips.py` | solo HTTP; no importa `runner` |

Después de cualquier cambio: `pytest -q`. Las pruebas del módulo están en
`tests/test_notificador_correo.py` y no usan red ni SMTP.

## 7. Archivos del módulo

| Archivo | Rol |
|---|---|
| `demo_analisis.py` | Lanzador de la interfaz `/analisis/` y controlador de la tanda |
| `demo_camara_ip.py` | Lanzador de la cámara IP con un video; `--probar-correo` |
| `outputs/notificador_correo.py` | Agrupación, imagen, PDF y envío SMTP (hilo propio) |
| `api/analisis_clips.py`, `api/static/analisis.html` | API y página de análisis |
| `api/operator_panel.py` | + `annotate_event()` (aditivo): estado del correo en la tarjeta |
| `api/static/operator.html` | Muestra ese estado en la tarjeta del evento |
| `config_demo_correo.json` | Cámara, sección `correo` y catálogo `clips` (sin secretos) |
| `scripts/armar_video_demo.py` | Arma el video de 5 caídas desde `data/goldset` |
| `requirements-demo-correo.txt` | Dependencias del módulo |

## 8. Problemas conocidos

- **`OSError: [Errno 2] No such file or directory: ...torch...LICENSE...` al instalar**: Windows
  limita las rutas a 260 caracteres y PyTorch trae archivos muy profundos. Tener el repositorio
  en una ruta corta (p. ej. `C:\Users\<usuario>\Documents\Vigilante-digital`) o habilitar
  rutas largas: https://pip.pypa.io/warnings/enable-long-paths
- **Versión de torch**: `requirements-academico.txt` no fija `torch`, así que una instalación
  nueva trae la última (2.15.0 el 22-11-2026; la laptop de Damián tiene 2.14.0). Las pruebas
  pasan con ambas; si los números del experimento no calzan, es lo primero que hay que fijar.

- **El video del panel se ve negro**: falta `uvicorn[standard]` (paso 2), o la pestaña quedó
  con la versión vieja: `Ctrl+Shift+R`.
- **`ModuleNotFoundError: lap`**: `pip install lapx==0.13.1` con el `.venv` activado.
  Si ultralytics lo instala solo, puede hacerlo en otro entorno, el del `pip` del PATH.
- **Gmail rechazó la clave**: la contraseña de aplicación se revocó o se copió mal. Se crea
  otra en https://myaccount.google.com/apppasswords (requiere verificación en 2 pasos).
- **La consola muestra `EmailSender inicializado sin credenciales`**: es el `TriggerManager`
  que crea `run_file`, que este módulo no usa. Se puede ignorar (deuda D1).
