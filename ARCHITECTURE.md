> **HISTÓRICO / parcial.** Reglas de capas vigentes están en `CODE_INDEX.md` y `.cursor/rules/`. Arquitectura de producto: `docs/REFORMULACION/05_ARQUITECTURA_Y_MEMORIA_SITIO.md`.

# Manifiesto de Arquitectura: Vigilante Digital IA

Este documento establece las reglas inviolables de diseño y desarrollo para el proyecto. Su objetivo es garantizar la modularidad, la mantenibilidad y preparar el sistema para una futura escalabilidad mediante contenedores (Docker).

**Tanto desarrolladores humanos como asistentes de IA (GitHub Copilot) deben adherirse estrictamente a estas directrices.**

## 1. Principios de Modularidad y Dependencias

El proyecto sigue una arquitectura en capas estricta para evitar el código "espagueti" y dependencias circulares.

### Reglas de Importación (Jerarquía):

* **Nivel Superior (Orquestación):** `main.py`.
    * PUEDE importar de: `core/`, `inputs/`, `outputs/`, `config.py`.
* **Nivel Medio (Lógica de Negocio/Dominio):** `core/`, `inputs/`, `outputs/`.
    * `core/` (El Cerebro): **NO DEBE** importar de `inputs/` ni de `outputs/`. Debe ser agnóstico a de dónde viene el video o a dónde va la alerta. Solo procesa datos.
    * `inputs/` y `outputs/`: Idealmente no deberían depender entre sí. Pueden importar utilidades de `core/` si es estrictamente necesario para definiciones de tipos o clases de datos comunes.
* **Nivel Transversal (Configuración):** `config.py`.
    * No debe depender de ningún otro módulo del proyecto.

> **Directriz para Copilot:** Si sugieres código en `core/pose_detector.py` que intenta importar algo como `outputs.email_sender`, DETENTE. Estás violando la arquitectura. La comunicación debe pasar siempre por `main.py`.

## 2. Estándares de Código (Vibe Coding Fuel)

Para maximizar la eficiencia del desarrollo asistido por IA y la robustez del código:

* **Regla de Oro: Type Hinting:** TODAS las definiciones de funciones y métodos (argumentos y retornos) deben estar tipadas explícitamente usando el módulo `typing` de Python.
    * *Incorrecto:* `def procesar(frame):`
    * *Correcto:* `def procesar(frame: np.ndarray) -> dict[str, Any]:`
* **Docstrings:** Todas las clases y funciones públicas deben tener docstrings en formato Google o NumPy, explicando parámetros, retornos y posibles excepciones.
* **Manejo de Errores:** Las operaciones de I/O (lectura de video, red, archivos, APIs externas) NUNCA deben estar en el flujo principal sin un bloque `try...except` robusto que capture fallos transitorios sin tumbar la aplicación.

## 3. Gestión de Configuración

* **Cero Hardcoding:** Ninguna credencial, dirección IP, ruta de archivo absoluta o token de API debe estar escrito directamente en el código fuente.
* **Centralización:** Todo debe leerse desde `config.py`.
* **Preparación para Docker:** El archivo `config.py` debe estar diseñado para leer preferentemente Variables de Entorno (`os.getenv`), usando valores por defecto solo para desarrollo local.

## 4. Estructura de Directorios Objetivo
vigilante_project/ ├── ARCHITECTURE.md # Este archivo. ├── README.md # Documentación general y stack. ├── main.py # Orquestador. ├── config.py # Variables y secretos. ├── requirements.txt # Dependencias congeladas. │ ├── core/ # [IA Pura] Lógica de detección y estado. │ ├── init.py │ └── pose_detector.py │ ├── inputs/ # [Fuentes] Abstracciones de video. │ ├── init.py │ └── video_stream.py │ └── outputs/ # [Alertas/Logs] Efectos secundarios. ├── init.py ├── alert_manager.py # (Futuro) Coordinador de alertas └── email_sender.py