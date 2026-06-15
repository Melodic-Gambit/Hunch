# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

mpl_datas, mpl_binaries, mpl_hiddenimports = collect_all('matplotlib')
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
pd_datas,  pd_binaries,  pd_hiddenimports  = collect_all('pandas')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=mpl_binaries + ctk_binaries + pd_binaries,
    datas=mpl_datas + ctk_datas + pd_datas + [('teal.json', '.'), ('Hunch.ico', '.'), ('audio-notification', 'audio-notification'), ('gf_logo.png', '.'), ('version.txt', '.')] + ([('app.png', '.')] if os.path.exists('app.png') else []),
    hiddenimports=mpl_hiddenimports + ctk_hiddenimports + pd_hiddenimports + [
        'pymysql',
        'psycopg2',
        'oracledb',
        'cx_Oracle',
        # GF.Scraping dependencies
        'requests',
        'bs4',
        'beautifulsoup4',
        'openpyxl',
        'openpyxl.utils',
        'openpyxl.styles',
        'pyperclip',
        # System tray
        'pystray',
        'pystray._win32',
        # SQL Выгрузка
        'widgets.sql_export_service',
        'widgets.sql_export_settings_dialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6', 'PyQt6', 'PySide2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='Hunch',
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
    icon=['Hunch.ico'],
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Hunch',
)

