@echo off
setlocal enabledelayedexpansion
title Juice | Render Manager for Blender - Build

echo.
echo  ============================================================
echo   Juice | Render Manager for Blender v1.0.0 - Build Script
echo   Franco Basualdo - Tryhard VFX
echo  ============================================================
echo.

:: ── 1. Verificar Python ──────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en el PATH.
    echo         Instala Python 3.10+ desde https://www.python.org/downloads/
    echo         Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] %PYVER% detectado.
echo.

:: ── 2. Ir al directorio del script ───────────────────────────────────────────
cd /d "%~dp0"

:: ── 3. Crear/usar entorno virtual local ──────────────────────────────────────
echo [1/6] Preparando entorno virtual local (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual .venv
        pause
        exit /b 1
    )
)
set "PYTHON_VENV=.venv\Scripts\python.exe"
echo [OK] Entorno virtual listo: %PYTHON_VENV%
echo.

:: ── 4. Actualizar pip en el entorno virtual ──────────────────────────────────
echo [2/6] Actualizando pip en .venv...
"%PYTHON_VENV%" -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [ERROR] Fallo al actualizar pip en .venv
    pause
    exit /b 1
)
echo [OK] pip actualizado en .venv
echo.

:: ── 5. Instalar dependencias de la app ───────────────────────────────────────
echo [3/6] Instalando dependencias de la app (PyQt6, Pillow) en .venv...
"%PYTHON_VENV%" -m pip install PyQt6 Pillow --quiet
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias en .venv.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

:: ── 6. Instalar PyInstaller en .venv ─────────────────────────────────────────
echo [4/6] Instalando PyInstaller en .venv...
"%PYTHON_VENV%" -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de PyInstaller en .venv.
    pause
    exit /b 1
)
echo [OK] PyInstaller listo.
echo.

:: ── 7. Limpiar builds anteriores ─────────────────────────────────────────────
echo [5/6] Construyendo ejecutable...
if exist "dist\Juice" (
    echo       Limpiando build anterior...
    rmdir /s /q "dist\Juice"
)
if exist "build\Juice" (
    rmdir /s /q "build\Juice"
)

:: ── 8. Ejecutar PyInstaller ──────────────────────────────────────────────────
"%PYTHON_VENV%" -m PyInstaller Juice.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller fallo. Revisa los mensajes de error arriba.
    pause
    exit /b 1
)

:: ── 9. Verificar resultado ───────────────────────────────────────────────────
if not exist "dist\Juice\Juice.exe" (
    echo [ERROR] No se encontro el ejecutable en dist\Juice\
    pause
    exit /b 1
)
echo [OK] Ejecutable generado correctamente.
echo.

:: ── 10. Compilar instalador con Inno Setup (si existe ISCC) ─────────────────
echo [6/6] Compilando instalador con Inno Setup...
set "ISCC_EXE="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
    echo [WARN] No se encontro ISCC.exe (Inno Setup 6).
    echo        El .exe de la app esta listo, pero el instalador no se compilo automaticamente.
    echo        Compila manualmente installer.iss desde Inno Setup Compiler.
) else (
    "%ISCC_EXE%" "installer.iss"
    if errorlevel 1 (
        echo [ERROR] Fallo la compilacion del instalador con Inno Setup.
        pause
        exit /b 1
    )
    echo [OK] Instalador compilado correctamente en la carpeta dist\
)

echo.
echo  ============================================================
echo   BUILD EXITOSO!
echo.
echo   Ejecutable app: dist\Juice\Juice.exe
echo   Instalador:     dist\Juice_Setup_v1.0.0.exe (si ISCC estaba disponible)
echo  ============================================================
echo.

:: ── 11. Abrir carpeta de salida ──────────────────────────────────────────────
set /p OPEN="Abrir carpeta dist\ ? [S/N]: "
if /i "!OPEN!"=="S" (
    explorer "dist"
)

endlocal
pause

