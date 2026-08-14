# -*- mode: python ; coding: utf-8 -*-
# Spec de la BUILD PC PARA TESTERS.
# Entra por rhythm_pc.py (flag RHYTHM_BUILD=pc) y excluye sounddevice.
#
# Decisiones anti-falso-positivo de antivirus (el exe daba "troyano"):
#   - onedir en vez de onefile: el auto-extraible de onefile se comporta
#     como un dropper y los AV lo flaggean por heuristica. Se distribuye
#     la carpeta dist/rhythm_testers comprimida en zip.
#   - upx=False: la compresion UPX es el trigger #1 de falsos positivos.
#   - version='version_pc.txt': metadatos de identidad (nombre, autor,
#     descripcion) — un exe anonimo es mas sospechoso que uno identificado.

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
    [],
    exclude_binaries=True,
    name='rhythm_testers',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['rhythm.ico'],
    version='version_pc.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='rhythm_testers',
)
