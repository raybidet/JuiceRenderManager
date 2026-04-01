# Juice | Render Manager for Blender

Gestor de renders para Blender. Aplicación desktop en Python con GUI para manejar trabajos de renderizado distribuidos usando workers.

## Características
- Interfaz gráfica (main_window.py)
- Modelos de datos (models.py)
- Workers para renderizado (worker.py)
- Construido con PyInstaller (exe disponible en build/)
- Soporte para jobs JSON (render_jobs.json)
- Addon Blender integrado (juice_addon/juice_render_manager_addon.py)

## Instalación
1. Instalar Python 3.10+
2. `pip install -r requirements.txt` (si existe)
3. Ejecutar `python app.py`

**O usar instalador:** `Juice_Setup_v1.0.0.exe`

## Build

### Opción recomendada (automática)
Ejecutar:

- `build.bat`

Este script ahora:
1. Crea/usa un entorno virtual local `.venv`
2. Instala dependencias en `.venv` (`PyQt6`, `Pillow`, `pyinstaller`)
3. Compila el ejecutable con `Juice.spec`
4. Si detecta Inno Setup 6 (`ISCC.exe`), compila también el instalador automáticamente desde `installer.iss`

Salidas esperadas:
- App: `dist\Juice\Juice.exe`
- Instalador: `dist\Juice_Setup_v1.0.0.exe` (si ISCC está disponible)

### Opción manual
- `pyinstaller Juice.spec --clean --noconfirm`
- Compilar `installer.iss` con Inno Setup Compiler (ISCC o GUI)

## Blender Addon
1. Abrir Blender
2. Edit → Preferences → Add-ons → Install
3. Seleccionar `juice_addon/juice_render_manager_addon.py`
4. Activar "Juice | Render Manager for Blender"
5. Panel en View3D → Sidebar → Juice

## Archivos principales
- **app.py**: Entrada principal
- **main_window.py**: Ventana principal
- **models.py**: Modelos de datos
- **worker.py**: Lógica de worker
- **ipc_server.py**: Servidor IPC para addon Blender

**Configuración persistida:** `%APPDATA%\Juice\render_jobs.json`

Proyecto en desarrollo - ver TODO.md para pendientes.

Logo by [creator if known].

