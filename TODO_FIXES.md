# Bug Fixes — Post-Migration Audit

## Bugs Identified

- [x] **BUG 1 (CRITICAL)** `main_window.py` — `_start_ipc_server()` uses `BRMIPCServer` (undefined) instead of `JuiceIPCServer`
- [x] **BUG 2 (MEDIUM)** `worker.py` — `get_blend_info()` uses `|` as field separator → switched to JSON output
- [x] **BUG 3 (MINOR)** `main_window.py` — Cache key uses `|` as separator in 3 places → switched to `\n`
- [x] **BUG 4 (INSTALLER)** `installer.iss` — `DefaultDirName` contains `|` (invalid Windows path char) → uses `AppDirName = "Juice Render Manager"`

## Progress

- [x] Fix BUG 1 in main_window.py — replaced `BRMIPCServer(...)` → `JuiceIPCServer(...)` in `_start_ipc_server()`
- [x] Fix BUG 2 in worker.py — rewrote Blender script to output JSON; updated parser; added `resolution_pct` field; added `import json`
- [x] Fix BUG 3 in main_window.py — changed 3 cache key f-strings from `f"{x}|{y}"` → `f"{x}\n{y}"`
- [x] Fix BUG 4 in installer.iss — added `#define AppDirName "Juice Render Manager"`; `DefaultDirName={autopf}\{#AppDirName}`

## ALL FIXES COMPLETE ✅
