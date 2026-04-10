# Juice | Render Manager for Blender — Project Context

## Estructura del proyecto
```
BlenderRenderManager/
├── app.py            # Entry point: QApplication + MainWindow
├── models.py         # RenderJob dataclass + JSON persistence
├── worker.py         # RenderWorker, build_render_script(), get_blend_info()
├── main_window.py    # PyQt6 MainWindow, signals, UI completa
├── render_jobs.json  # Cola persistida (se crea automáticamente)
└── CLAUDE.md         # Este archivo
```

## Stack
- Python 3.10+, PyQt6 (reemplazó Tkinter — ver por qué abajo)
- Pillow (preview de frames, opcional)
- Sin más dependencias externas

## Por qué PyQt6 y no Tkinter
Tkinter en Windows comparte el event loop con el sistema de ventanas de Win32.
Cualquier operación > ~50ms en el hilo principal (insertar texto, actualizar tabla)
congela la ventana completamente — el usuario no puede moverla, minimizarla ni
interactuar. PyQt6 tiene su propio event loop separado de Win32 y usa QThread +
pyqtSignal para comunicación entre hilos, eliminando el problema de raíz.

## Arquitectura de threading
- `RenderThread(QThread)` corre `RenderWorker.run()` en un hilo separado.
- `WorkerSignals(QObject)` define las señales Qt:
  - `log_line(job_id, str)` — cada línea de stdout de Blender
  - `progress(job_id)` — frame actualizado (throttled 250ms en worker)
  - `frame_saved(job_id)` — frame guardado a disco
  - `done(job_id, status)` — render terminado/error/cancelado
- Las señales se emiten desde el thread worker y PyQt6 las despacha al hilo
  principal de forma thread-safe automáticamente.
- `BlendInfoThread(QThread)` hace la consulta headless de escenas/samples sin
  bloquear la UI.

## Problema central: GPU en background mode
Blender `--background` NO carga `userpref.blend`. La solución:
1. `build_render_script()` genera un `.py` temporal.
2. Blender lo ejecuta con `--python <tmp>` ANTES de `--render-anim`.
3. El script llama `bpy.ops.wm.read_userpref()` + `cprefs.get_devices()`.
4. Lee `compute_device_type` y devices habilitados → setea `scene.cycles.device`.
5. El device detectado se parsea del log (`[BRM] cycles.device = GPU`) y se
   muestra en el panel de progreso en tiempo real.

## RenderJob — campos clave
- `sequence_name`: nombre de la secuencia, usado como subdirectorio de output.
  `effective_output_path` = `output_path / sequence_name` (si está seteado).
- `samples_override`: int o None (None = usar lo del .blend).
- `_detected_device`: atributo dinámico seteado al parsear el log, muestra
  "GPU" o "CPU" en el panel de progreso.

## Paths importantes
- Blender default: `F:\Program Files\blender.exe`
- Config: `render_jobs.json` (mismo directorio que los scripts)
- Scripts temporales: `tempfile.NamedTemporaryFile` sufijo `_brm.py`, se borran
  en el `finally` del worker.

## Estilo visual
Catppuccin Mocha — paleta definida en `main_window.py` dict `C`.
El stylesheet completo está en `STYLESHEET` en el mismo módulo.

## Preferencias del usuario
- Windows 10, NVIDIA GPU (OptiX/CUDA)
- Blender en `F:\Program Files\blender.exe`
- Prefiere respuestas en español y código modular
- No es necesario mantener todo en un archivo único

## Consejos para el flujo de trabajo (ver sección abajo)
Ver sección "Consejos de producción" al final de este documento.

## Cosas a mejorar / pendientes
- Preview de `.exr`: QPixmap no los soporta nativamente; el fallback Pillow
  necesita pillow-avif-plugin o similar con soporte OpenEXR.
- Notificación al terminar un job (sonido o notificación de Windows).
- Drag & drop de archivos .blend sobre la ventana.
- Estimado de tiempo mejorado: actualmente usa promedio simple; podría usar
  las últimas N frames para adaptarse a cambios de complejidad.

---

## Consejos de producción

### Organización de renders
Usar siempre **Sequence Name** para nombrar la secuencia. Esto crea subcarpetas
automáticas en el output:
```
/renders/
  shot_010/frame_0001.png
  shot_020/frame_0001.png
```
Así nunca se mezclan frames de distintas tomas.

### Samples para draft vs final
Agregar el mismo job dos veces con distintos samples:
- Draft: 64 samples → output en `/renders/draft/shot_010/`
- Final: 512 samples → output en `/renders/final/shot_010/`
Permite revisar composición rápido antes del render final.

### GPU: verificar siempre en el log
Buscar en el Job Log la línea:
```
[BRM] cycles.device  = GPU
[BRM] Active devices: NVIDIA GeForce RTX XXXX
```
Si dice `CPU`, el userpref.blend no se cargó. Solución: abrir Blender normal,
ir a Edit > Preferences > System > Cycles Render Devices, activar la GPU,
guardar preferencias (Ctrl+U) y volver a lanzar el render desde el manager.

### Orden de la cola
Conviene ordenar los jobs de más cortos a más largos cuando se usa
"Start All Pending". Los jobs cortos dan feedback rápido de que todo funciona
antes de lanzar los más pesados.
