# Agente de triaje de incidentes — TI2082

Agente que convierte una detección de caída en un reporte de incidente
redactado y notificado, con aprobación humana antes de registrar.

Independiente del pipeline de detección: recibe un evento JSON.

## Estructura

    agente/
      main.py            punto de entrada y bucle del agente
      herramientas.py    las cuatro herramientas
      politica.py        respaldo determinista por reglas
      prompts.py         instrucciones del sistema
      traza.py           registro paso a paso
    datos_ficticios/
      turnos.csv
      historial_eventos.json
      evento_normal.json
      evento_malicioso.json

Sin frameworks de agentes. Sin orquestadores. Sin base de datos nueva.

## Entrada

    {
      "evento_id": "EV-2026-0412",
      "camara": "CAM_PASILLO_B",
      "zona": "Pasillo ala B",
      "hora_local": "2026-11-12T03:14:00-03:00",
      "duracion_s": 47.2,
      "se_levanto": false,
      "senal": "detector"
    }

## Herramientas

| Nombre | Qué hace | Permiso |
|---|---|---|
| consultar_turno(hora) | Quién estaba de turno y cuántos eran | solo lectura |
| consultar_historial(zona, dias) | Incidentes previos en esa zona | solo lectura |
| registrar_incidente(reporte) | Escribe en el registro | tras aprobación |
| enviar_notificacion(dest, asunto, cuerpo) | Envía el aviso | tras aprobación |

Las dos de escritura no reciben credenciales hasta que una persona
aprueba. No es una convención: el objeto de credenciales se construye
después del punto de aprobación.

## Decisión

Tres vías, lista cerrada:

- escalamiento_inmediato — episodio largo sin levantarse, o turno de
  noche con un solo funcionario, o tercer incidente de la semana en
  esa zona. Notifica al turno y a coordinación, prioridad alta.
- reporte_rutina — caso sin agravantes. Notifica solo al turno.
- probable_falso_positivo — episodio corto y la persona se levantó
  sola. No genera reporte, solo registra para revisión.

Cada vía usa un conjunto distinto de herramientas.

## Respaldo determinista

Si falta la clave, no hay red, o el modelo devuelve algo fuera de la
lista cerrada, se aplica:

- duracion_s >= 20 y no se_levanto -> escalamiento_inmediato
- turno de noche con un solo funcionario -> escalamiento_inmediato
- tercer incidente o más en esa zona en 7 días -> escalamiento_inmediato
- duracion_s < 5 y se_levanto -> probable_falso_positivo
- resto -> reporte_rutina

Las reglas se evalúan en ese orden y gana la primera que se cumple:
un agravante de escalamiento prevalece sobre un probable falso
positivo. El turno sale de consultar_turno y el conteo de incidentes
de consultar_historial más el evento actual. Si una herramienta no
respondió, la regla que depende de ella no se cumple y se anota.

Y se anota en la traza que la decisión vino de reglas, no del modelo,
y cuál regla disparó. El agente nunca queda sin decidir.

## Seguridad frente a inyección

Lo que devuelven las herramientas y los campos de texto del evento se
entregan al modelo delimitados y etiquetados como contenido no
confiable. La acción devuelta se valida contra la lista cerrada de
tres vías; cualquier otra cosa cae al respaldo por reglas.

Si se detecta texto con forma de instrucción en un campo de entrada,
se registra en la traza.

## Topes

- 5 llamadas al modelo por ejecución
- 8 pasos por ejecución
- 60 segundos de timeout

## Traza

salida/traza/<evento_id>.jsonl, un registro por paso: herramienta
llamada, qué devolvió, decisión, justificación, y si vino del modelo
o de las reglas.

## Claves

En variable de entorno. Nunca en el código, nunca en el prompt,
nunca en un archivo versionado. Agregar .env al .gitignore.

## Límites

El agente no contacta familiares ni emergencias, no accede a ficha
clínica, no modifica la planilla de turnos, no envía ni registra sin
aprobación, y no ve imágenes ni video.