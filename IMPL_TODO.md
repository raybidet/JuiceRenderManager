# Implementación — Sesión 1 (Alta Prioridad)

## Tareas

- [x] **worker.py** — Agregar FPS por escena en `get_blend_info`
- [x] **main_window.py** — Imports: `winsound`, `sys`, `subprocess` directo
- [x] **main_window.py** — Clase `ConvertThread(QThread)`
- [x] **main_window.py** — `__init__`: `setAcceptDrops(True)`, `_convert_thread`
- [x] **main_window.py** — Botones Retry y Duplicate en `btn_row`
- [x] **main_window.py** — Sección "Export / Convert to MP4" en panel derecho
- [x] **main_window.py** — Métodos: `_retry_selected`, `_duplicate_selected`
- [x] **main_window.py** — Métodos: `_convert_to_mp4`, `_on_convert_done`
- [x] **main_window.py** — Método: `_play_queue_done_sound`
- [x] **main_window.py** — `_on_job_done`: check all done → play sound
- [x] **main_window.py** — `_on_job_select`: enable/disable Convert button
- [x] **main_window.py** — `_apply_blend_info`: guardar FPS map
- [x] **main_window.py** — `dragEnterEvent` / `dropEvent`
- [x] **main_window.py** — `closeEvent`: cleanup `_convert_thread`
- [x] **TODO.md** — Marcar 5 features como completadas

---

# Implementación — Sesión 2 (Media / Baja / UX)

## Tareas

- [x] **worker.py** — ETA mejorada: rolling window de últimas 8 frames
- [x] **main_window.py** — Import `ctypes` y `html`
- [x] **main_window.py** — Columna "Samples" en QTreeWidget
- [x] **main_window.py** — Log con colores: `_log_line_color()` + `_append_log_line()`
- [x] **main_window.py** — Botón "📂 Open Folder" en panel derecho
- [x] **main_window.py** — Método `_open_output_folder()`
- [x] **main_window.py** — Botón "⏸ Pause/Resume" en btn_row
- [x] **main_window.py** — Método `_toggle_pause_selected()` con ctypes
- [x] **main_window.py** — Confirmar antes de eliminar en `_remove_selected`
- [x] **main_window.py** — Botones "↑" "↓" en btn_row
- [x] **main_window.py** — Métodos `_move_job_up()` / `_move_job_down()`
- [x] **TODO.md** — Marcar ítems completados
- [x] **IMPL_TODO.md** — Marcar sesión 2 como completada

---

# Implementación — Sesión 3 (Media prioridad)

## Tareas

- [x] **main_window.py** — Import `QStyledItemDelegate`
- [x] **main_window.py** — Clase `BlenderDelegate` (QComboBox por fila en columna Blender)
- [x] **main_window.py** — `setItemDelegateForColumn(3, BlenderDelegate(...))`
- [x] **main_window.py** — Guardar `job_id` en `Qt.ItemDataRole.UserRole` por fila
- [x] **main_window.py** — Método `_on_table_blender_changed(job_id, profile_name)` dentro de `MainWindow`
- [x] **main_window.py** — Persistencia automática con `save_config` al cambiar selector
