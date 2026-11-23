# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from PyInstaller.utils.hooks import collect_data_files


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('ui', 'ui')] + collect_data_files('tzdata'),
    hiddenimports=['fdb', 'tzdata', 'palmapp', 'eleventa'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SistemaTickets',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icono.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SistemaTickets',
)

# Junto al .exe (no dentro de _internal): el cliente de Firebird y la configuración de fábrica.
destino = os.path.join(DISTPATH, 'SistemaTickets')
if os.path.isdir('firebird'):
    shutil.copytree('firebird', os.path.join(destino, 'firebird'), dirs_exist_ok=True)
else:
    print('AVISO: falta la carpeta firebird (cliente de Firebird): sin ella no se lee eleventa. Ver README.')
if not os.path.exists(os.path.join(destino, 'config.json')):
    # La de esta PC (con la API key) o, en un clon del repo, el ejemplo para llenarlo.
    shutil.copy('config.json' if os.path.exists('config.json') else 'config.ejemplo.json', os.path.join(destino, 'config.json'))
