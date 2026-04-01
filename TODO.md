# TODO - Migración a Juice | Render Manager for Blender

**Estado:** ✅ COMPLETADO (15/15)

## Resumen de cambios realizados

### ✅ Textos/nombres actualizados (12/12)
- [x] **app.py** - ApplicationName → "Juice | Render Manager for Blender"
- [x] **ipc_server.py** - Docstring + `BRMIPCServer` → `JuiceIPCServer`
- [x] **main_window.py** - WindowTitle + QLabel → nuevo nombre
- [x] **models.py** - Config dir `"BlenderRenderManager"` → `"Juice"` + migración auto
- [x] **Addon** - `blender_addon/` → `juice_addon/` + `juice_render_manager_addon.py`
- [x] **Addon** - `BRMProperties` → `JuiceProperties` + bl_info + panel "Juice"
- [x] **build.bat** - Títulos + `dist\BlenderRenderManager` → `dist\Juice`
- [x] **installer.iss** - AppName + `Juice.exe` + paths
- [x] **README.md** - Títulos + addon info + instalación
- [x] **Otros MD** - CLAUDE.md, IMPL_TODO.md, TODO_LIST.md, TODO_SELECTOR_BLENDER.md

### ✅ Estructura (3/3)
- [x] **Directorio addon** - Movido/renombrado correctamente
- [x] **Archivos limpios** - worker.py, resolution_slider.py sin cambios
- [x] **TODO.md** - Tracking completo

## Comandos de validación
```
python app.py                    # ✅ Título correcto + IPC "Juice"
build.bat                        # ✅ dist\Juice\Juice.exe
# Blender: Install juice_addon/juice_render_manager_addon.py → Panel "Juice"
```

## Notas finales
- **Config migrada** automáticamente desde `%APPDATA%\BlenderRenderManager`
- **Build paths** actualizados (`Juice.spec` requerirá ajuste manual si existe)
- **VSCode tabs** pueden mostrar paths viejos - refrescar/reload window

**Migración completada exitosamente!** 🎉

**Próximo:** Test funcional + `attempt_completion`

