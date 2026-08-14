# -*- mode: python ; coding: utf-8 -*-
# Spec de la BUILD PC PARA TESTERS (dist/rhythm_testers.exe).
# Entra por rhythm_pc.py (flag RHYTHM_BUILD=pc) y excluye sounddevice:
# esta build no tiene modo instrumento ni line-in.

a = Analysis(
    ['rhythm_pc.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['sounddevice'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='rhythm_testers',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['rhythm.ico'],
)
