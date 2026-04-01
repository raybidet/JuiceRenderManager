@echo off
setlocal enabledelayedexpansion
title Juice Render Manager for Blender - Build

echo.
echo  ============================================================
echo   Juice Render Manager for Blender - Build Script
echo   Franco Basualdo - Tryhard VFX
echo  ============================================================
echo.

REM Ir al directorio del script
cd /d "%~dp0"

REM 1) Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en PATH.
    echo         Instala Python 3.10+ y marca "Add Python to PATH".
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] %PYVER%
echo.

REM 2) Crear/usar .venv
echo [1/7] Preparando entorno virtual (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear .venv
        pause
        exit /b 1
    )
)
set "PYTHON_VENV=.venv\Scripts\python.exe"
echo [OK] Entorno virtual listo.
echo.

REM 3) Actualizar pip
echo [2/7] Actualizando pip...
"%PYTHON_VENV%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Fallo al actualizar pip.
    pause
    exit /b 1
)
echo [OK] pip actualizado.
echo.

REM 4) Instalar dependencias
echo [3/7] Instalando dependencias...
"%PYTHON_VENV%" -m pip install PyQt6 Pillow pyinstaller
if errorlevel 1 (
    echo [ERROR] Fallo instalando dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

REM 5) Limpiar salida anterior
echo [4/7] Limpiando builds anteriores...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo [OK] Limpieza completada.
echo.

REM 6) Build con PyInstaller (sin .spec fijo)
echo [5/7] Generando ejecutable con PyInstaller...

"%PYTHON_VENV%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --name "Juice" ^
  --windowed ^
  --icon "logo.ico" ^
  --add-data "logo.png;." ^
  "app.py"

if errorlevel 1 (
    echo [ERROR] PyInstaller falló.
    pause
    exit /b 1
)

if not exist "dist\Juice\Juice.exe" (
    echo [ERROR] No se encontró dist\Juice\Juice.exe tras el build.
    pause
    exit /b 1
)
echo [OK] Ejecutable generado: dist\Juice\Juice.exe
echo.

REM 7) Compilar instalador con Inno Setup
echo [6/7] Compilando instalador (Inno Setup)...
set "ISCC_EXE="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
    echo [WARN] No se encontró ISCC.exe.
    echo        El ejecutable está listo en dist\Juice\Juice.exe
    echo        Compila manualmente installer.iss desde Inno Setup Compiler.
) else (
    "%ISCC_EXE%" "installer.iss"
    if errorlevel 1 (
        echo [ERROR] Falló la compilación de installer.iss
        pause
        exit /b 1
    )
)

echo [7/7] Verificando instalador...
if exist "dist\Juice_Setup_v1.1.0.exe" (
    echo [OK] Instalador generado: dist\Juice_Setup_v1.1.0.exe
) else (
    echo [WARN] No se encontró dist\Juice_Setup_v1.1.0.exe
    echo        Revisa OutputBaseFilename/AppVersion en installer.iss
)

echo.
echo  ============================================================
echo   BUILD FINALIZADO
echo   Ejecutable: dist\Juice\Juice.exe
echo   Instalador: dist\Juice_Setup_v1.1.0.exe
echo  ============================================================
echo.

set /p OPEN_DIST="Abrir carpeta dist\ ? [S/N]: "
if /i "!OPEN_DIST!"=="S" explorer "dist"

endlocal
pause
