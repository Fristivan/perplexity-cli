# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# Дособираем Rich, включая unicode-таблицы, которые у тебя ломались
rich_datas, rich_binaries, rich_hidden = collect_all("rich", include_py_files=True)
rich_hidden += collect_submodules("rich._unicode_data", on_error="ignore")
rich_datas += collect_data_files("rich._unicode_data", include_py_files=True)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=rich_binaries,
    datas=rich_datas,
    hiddenimports=rich_hidden,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ppl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    exclude_binaries=False,  # важно для onefile
)
