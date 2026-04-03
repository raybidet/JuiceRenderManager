# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for macOS App Bundle
# Usage: pyinstaller macos.spec --clean --noconfirm
# Results in dist/Juice.app (universal2 for Intel/Apple Silicon)

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('logo.ico', '.'),
        ('logo.png', '.'),
        ('blender_addon', 'blender_addon'),
        ('juice_addon', 'juice_addon'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        'PIL',
        'PIL.Image',
        'PIL.ImageQt',
        'PIL._tkinter_finder',  # macOS Tk fallback
        'dataclasses',
        'ctypes',
    ],
    hookspath=[],
    hooksconfig={
        'PyQt6': {
            'qt_plugins': [
                'platforms/qminimal.dylib',     # Minimal platform plugin
                'imageformats/qjpeg.dylib',
                'imageformats/qico.dylib', 
                'imageformats/qgif.dylib',
                'imageformats/qicns.dylib',     # macOS native
            ],
            'exclude_styles': ['macos-native'],
            'compat': True,
        },
    },
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Juice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal on launch
    target_arch='universal2',  # Intel + Apple Silicon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Juice',
)

# Create macOS .app bundle (PyInstaller 6 compatible)
app = BUNDLE(
    coll,
    name='Juice.app',
    icon='logo.ico',
    bundle_identifier='com.tryhardvfx.juice-rendermanager',
    info_plist={
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'NSPrincipalClass': 'NSApplication',
        'LSMinimumSystemVersion': '10.15',  # Catalina+
    },
)

