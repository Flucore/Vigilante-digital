# Deuda técnica — correo y demo con cámara IP simulada

Rama: `demo-correo` · Fecha: 2026-11-22

## Decisión

Para la presentación se necesita mostrar el envío automático de correo sin
hacer cambios estructurales antes de la defensa (`runner.py`, el detector y
`eval/` están congelados). Se resolvió con un **módulo aislado**:

| Archivo | Rol |
|---|---|
| `demo_camara_ip.py` | Lanzador: un video como cámara IP + panel + correo. Reutiliza `_start_panel` de `demo_panel.py`. |
| `outputs/notificador_correo.py` | Agrupa fragmentos (una caída = un correo), tope por sesión, PDF + envío en hilo propio, modo simulado. |
| `config_demo_correo.json` | Una cámara (`CAM_IP_01`), sección `correo`. `triggers` apagado a propósito. |
| `scripts/armar_video_demo.py` | Arma `data/demo/caidas_demo_30s.mp4` (5 caídas VP de bbox + separadores ADL VN). No es parte del experimento. |
| `api/operator_panel.py` | + `annotate_event()` (aditivo): muestra el estado del correo en la tarjeta. |
| `api/static/operator.html` | Muestra `evt.correo` en la tarjeta del evento. |
| `demo_analisis.py` | Interfaz web `/analisis/`: analiza los clips del catálogo (`config_demo_correo.json` → `clips`) como la cámara `CAM_IP_01`, uno tras otro, con resultado esperado vs. obtenido y estado de cada correo. |
| `api/analisis_clips.py` + `api/static/analisis.html` | Página y API de esa interfaz. Solo HTTP: el controlador lo inyecta el lanzador (no importa runner). |

El módulo se engancha a `runner.set_event_sink` y llama a `run_file` con
`dispatch_triggers=False`. **No pasa por `TriggerManager`.** La deuda de
abajo queda sin resolver en el camino original.

## Incoherencias encontradas (sin resolver)

| # | Dónde | Problema | Cómo lo esquiva el módulo |
|---|---|---|---|
| D1 | `outputs/email_sender.py` vs `.env.example` | EmailSender lee `GMAIL_SENDER_EMAIL`/`GMAIL_APP_PASSWORD`; `.env.example` documenta `SMTP_USER`/`SMTP_PASSWORD`/`EMAIL_RECIPIENTS`. Llenar el `.env` según el ejemplo no hace funcionar el correo. | Acepta ambos nombres y pasa las credenciales explícitas a EmailSender. |
| D2 | Todo el proyecto | Nadie carga `.env` (`python-dotenv` llega instalado por `uvicorn[standard]` pero no se usa ni está en requirements). | `cargar_env()` propio, sin dependencias. |
| D3 | `outputs/trigger_manager.py` | Un solo destinatario (`triggers.email.recipient` en el JSON), no `EMAIL_RECIPIENTS`. | Lista de destinatarios desde `.env` + `--para`. |
| D4 | Detector / `EventLogger` | Una caída se cierra y reabre en < 1 s: el video de demo da **12 episodios para 5 caídas**. Con triggers activos serían 12 correos. `EVENT_DEDUP_WINDOW_SEC` no los une. No afecta al experimento (cuenta la primera alarma por clip). | `AgrupadorCaidas`: une episodios a < 3 s (tiempo de video) del anterior. |
| D5 | `TriggerManager` | Sin tope ni enfriamiento: con `--loop` envía un correo por vuelta, para siempre. Además se crea uno por `run_file` (uno por cámara en el panel). | Tope por sesión (`max_correos_por_sesion`). |
| D6 | `outputs/report_generator.py` | Imprime la hora del evento en UTC y el pie con `datetime.now(timezone.utc)`. | Entrega al PDF los tiempos convertidos a la zona del config. El pie sigue en UTC. |
| D7 | `outputs/report_generator.py` | "Duración de la caída" es la del fragmento, no la de la caída completa (consecuencia de D4). | — |
| D8 | HUD / snapshot del runner | Con `--metodo bbox` la foto muestra "Evaluando n/8" (rótulo de pose), y como se toma al **cerrar** el episodio puede decir "Sin caída" con la persona en el suelo. | El correo usa el cuadro limpio del video en `end_frame`, enmarca `metadata.bbox` y agrega su propia franja (hora + ubicación). El PDF sigue usando la foto del runner. |
| D11 | `outputs/email_sender.py` | Solo texto plano + PDF; no admite imagen en línea ni varios destinatarios explícitos. | El notificador arma su propio `EmailMessage` (HTML + imagen CID + PDF) y usa `smtplib` directo. |
| D12 | Detector (bbox) | Fragmentos falsos de ~0,2 s cuando alguien entra agachado o al borde del cuadro (clips propios 08 y 12). | Duración mínima acumulada de 0,5 s antes de avisar (`correo.duracion_minima_s`). |
| D13 | Detector | Falsos negativos con oclusión (clip propio 09, palmera) y falsa alarma con postura de plancha (clip 14), en ambos criterios. | — Se muestran tal cual en la interfaz: son resultados, no errores de la demo. |
| D9 | `requirements.txt` | `playsound` no compila en Python 3.12 (y no se usa); `mediapipe` trae `opencv-contrib-python` 4.11 que tapa al `opencv-python==4.10` fijado; falta `lapx` (ultralytics lo autoinstala con el `pip` del PATH, que puede ser otro entorno). | — (ver manual de instalación) |
| D10 | `run_file` | Procesa todos los cuadros a la velocidad de la CPU (~7 fps en esta laptop): el video de 34 s tarda ~2 min 20 s. Una cámara IP real descartaría cuadros. | Aceptado para la demo: deja ~25 s entre caídas para narrar. |

## Para cerrar la deuda (después de la defensa)

1. Unificar nombres de variables de correo y cargar `.env` en un solo punto.
2. Mover agrupación + tope a `TriggerManager` (o a la capa de despacho) y eliminar el notificador de demo.
3. Corregir la fragmentación de episodios en el detector/EventLogger **con medición** (cambia la cuenta de eventos, no la de alarmas por clip).
4. Hora local en `ReportGenerator`; rótulo del HUD según método.
5. Limpiar `requirements.txt` y fijar `lapx` en `requirements-academico.txt`.
