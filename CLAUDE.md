# Vigía Digital

Proyecto de título de Ingeniería en Informática, INACAP 2026.
Equipo: Víctor Bonta, Víctor Sepúlveda, Damián Fierro.
Rama de trabajo: academico

## Qué es esto

Sistema de detección automática de caídas de pacientes mediante visión
computacional, para unidades de hospitalización de salud mental.
Procesa video de cámaras IP ya instaladas, en un nodo local.

## Qué se está investigando

Esto NO es un proyecto de producto: es un experimento comparativo.

Pregunta de investigación: ¿en qué medida un criterio sobre pose con
confirmación temporal reduce la tasa de falsas alarmas frente a un
criterio geométrico instantáneo, manteniendo la sensibilidad?

Brazos del experimento:
- bbox — criterio geométrico instantáneo sobre el rectángulo
  delimitador. Es la referencia: NO modificar su lógica.
- pose con ventana N — criterio sobre puntos clave con confirmación
  temporal.

Métricas: sensibilidad, falsas alarmas por cámara-hora, latencia.
Conjunto de validación: 70 clips de UR Fall (30 caídas, 40 ADL).

## Alcance actual

Tres líneas de trabajo, en este orden de prioridad:

1. Experimento comparativo (eval/) — es la tesis. No tocar su lógica
   de medición por ningún motivo.
2. Panel de operador (api/operator_panel.py + api/static/operator.html)
   — existe y está desconectado. Falta conectarlo a runner.py.
3. Agente de triaje (agente/) — proyecto de la asignatura TI2082.
   Independiente: opera sobre eventos JSON sintéticos, no sobre el
   pipeline de detección.

No implementar: zonas configurables, gestión de usuarios, autenticación
del panel forense, persistencia en Postgres.

El agente usa solo datos ficticios. Nunca clips de UR Fall ni datos de
personas reales.

## Entorno

- Python 3.12 (no 3.13 ni 3.14: PyTorch no es compatible)
- Entorno virtual en .venv
- PEP 8. Nombres de variables y funciones en inglés, comentarios y
  docstrings en español.

## Reglas de trabajo

- No tocar la lógica del criterio geométrico de referencia.
- Los umbrales van en archivo de configuración, nunca incrustados.
- Claves de API en variables de entorno, nunca en el código ni en
  archivos versionados.
- No subir al repositorio: .venv, clips de video, modelos .pt,
  archivos .env, direcciones IP de cámaras.
- Cambios chicos y revisables. Nada de refactorizaciones masivas.