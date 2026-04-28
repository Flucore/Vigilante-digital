# Funciones del Humano en la Maqueta

## Rol General

El humano no compite con la IA. El humano enseña, valida y decide. El sistema funciona como un vigilante digital que mira 24/7, pero la autoridad final en una maqueta y en pilotos reales debe ser humana.

## Funciones Antes de la Demo

### Preparar entorno

- Verificar iluminación.
- Verificar que las cámaras apunten a la zona correcta.
- Revisar que los celulares/cámaras estén en la misma red que el PC.
- Confirmar que las URLs de `demo_config.json` estén actualizadas.
- Probar el demo al menos 30 minutos antes.

### Calibrar regiones

- Para semáforo/luz: ajustar `roi`.
- Para polera roja: ajustar `roi` y `min_area_ratio`.
- Para perímetro: ajustar `perimeter_line`.
- Para caída: revisar distancia cámara-persona.

## Funciones Durante la Demo

### Operador técnico

- Arrancar `start_demo.bat`.
- Confirmar que la vista split esté estable.
- Presionar `f` para pantalla completa.
- Presionar `p` para generar PDF al detectar evento.
- Presionar `s` para screenshot manual.
- Presionar `r` si se requiere limpiar alertas visuales.

### Actor de prueba

- Simular caída de forma segura sobre colchoneta o superficie blanda.
- Entrar al cuadro con polera roja y permanecer 1 segundo.
- Cambiar color de luz/semaforo de forma visible dentro de la ROI.

### Narrador comercial

Debe explicar que:

- La IA no reemplaza al guardia: lo multiplica.
- El sistema detecta eventos, no solo graba video.
- Cada evento genera evidencia y puede activar protocolos.
- La empresa de seguridad puede aportar entornos reales para documentar casos.

## Funciones Después de la Demo

### Validación humana

- Revisar snapshots.
- Revisar PDFs.
- Marcar detecciones correctas e incorrectas.
- Guardar ejemplos útiles para dataset.

### Etiquetado de aprendizaje

Usar las imágenes guardadas para construir dataset:

- `fall`
- `normal`
- `red_shirt`
- `not_red_shirt`
- `traffic_red`
- `traffic_yellow`
- `traffic_green`
- `perimeter_breach`

### Decisión de mejora

Para cada error observado:

1. ¿Fue problema de cámara?
2. ¿Fue problema de iluminación?
3. ¿Fue problema de ROI/configuración?
4. ¿Requiere modelo entrenado?
5. ¿Debe agregarse regla temporal?

## Principio de Trabajo

El humano es el supervisor de aprendizaje. La maqueta debe generar evidencia suficiente para que el sistema aprenda de instalaciones reales sin exponer datos innecesarios ni romper cumplimiento legal.

