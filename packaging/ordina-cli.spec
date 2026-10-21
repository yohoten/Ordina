# -*- mode: python ; coding: utf-8 -*-
"""
Ordina CLI 打包规格（命令行版，保留控制台）
=========================================
产物：
    onedir  → dist/Ordina-cli/ordina-cli.exe
    onefile → dist/ordina-cli.exe        （设环境变量 ORDINA_ONEFILE=1 时）

与 GUI 版的差异：不打包 tkinter，体积约为 GUI 版的一半不到；
用法完全一致，只是前面不需要写 "cli"。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(SPEC)))
from spec_common import configure

cfg = configure(SPEC, include_ui=False)
ONEFILE = os.environ.get("ORDINA_ONEFILE") == "1"

block_cipher = None

a = Analysis(
    [os.path.join(cfg["packaging"], "cli_entry.py")],
    pathex=[cfg["root"]],
    binaries=[],
    datas=cfg["datas"],
    hiddenimports=cfg["hidden"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=cfg["excludes"],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name="ordina-cli",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=True,
        icon=cfg["icon"],
        version=cfg["version_file"],
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="ordina-cli",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        icon=cfg["icon"],
        version=cfg["version_file"],
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,
        name="Ordina-cli",
    )
