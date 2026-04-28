@echo off
chcp 65001 > nul
title Vigilante Digital IA — Demo

echo.
echo ============================================================
echo   VIGILANTE DIGITAL IA — Sistema de Vigilancia con IA
echo   Iniciando demo de 2 camaras IP...
echo ============================================================
echo.

:: Verificar que Python esté disponible
python --version > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python no encontrado. Instalar Python 3.10+
    pause
    exit /b 1
)

:: Ir al directorio raíz del proyecto (donde está este .bat)
cd /d "%~dp0"

:: Verificar dependencias críticas
echo [VERIFICANDO] Dependencias...
python -c "import cv2, mediapipe, numpy" > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INSTALANDO] Dependencias base...
    pip install -r requirements.txt --quiet
)

:: Verificar GPU (informativo)
echo [GPU] Verificando aceleracion...
python -c "import torch; print('  GPU disponible:', torch.cuda.get_device_name(0))" 2>nul || echo   CPU mode (sin PyTorch/CUDA)

echo.
echo [CONFIG] Usando: demo_config.json
echo [TECLAS] q=salir  p=PDF  s=screenshot  r=reset  f=fullscreen  ESPACIO=pausa
echo.
echo ============================================================
echo   Abre IP Webcam en los celulares y verifica las IPs en
echo   demo_config.json antes de continuar.
echo ============================================================
echo.

:: Opción para cambiar URLs rápido desde la línea de comandos
:: Ejemplo: start_demo.bat 192.168.1.5 192.168.1.6
set CAM1_IP=%1
set CAM2_IP=%2

if not "%CAM1_IP%"=="" (
    echo [CAM1] URL: http://%CAM1_IP%:8080/video
    echo [CAM2] URL: http://%CAM2_IP%:8080/video
    python scripts/demo_2cam.py --cam1 "http://%CAM1_IP%:8080/video" --cam2 "http://%CAM2_IP%:8080/video"
) else (
    python scripts/demo_2cam.py
)

echo.
echo ============================================================
echo   Demo finalizado.
echo   Revisa test_outputs/ para reportes y snapshots.
echo ============================================================
echo.
pause
