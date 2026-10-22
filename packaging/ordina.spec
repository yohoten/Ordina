# -*- mode: python ; coding: utf-8 -*-
"""
Ordina GUI 打包规格（图形界面，无控制台窗口）
=============================================
产物：
    onedir  → dist/Ordina/Ordina.exe
    onefile → dist/Ordina.exe          （设环境变量 ORDINA_ONEFILE=1 时）

压缩：
    upx 参数由 build.ps1 探测后通过 --upx-dir 传入；找不到 UPX 时
    PyInstaller 会自动跳过压缩，不影响构建。

用法（一般由 build.bat / build.ps1 调用）：
    python -m PyInstaller --noconfirm --distpath dist --workpath build/gui packaging/ordina.spec
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(SPEC)))
from spec_common import configure

cfg = configure(SPEC)
ONEFILE = os.environ.get("ORDINA_ONEFILE") == "1"

block_cipher = None

a = Analysis(
    [os.path.join(cfg["packaging"], "gui_entry.py")],
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
    # 单文件：所有依赖压进 exe，启动时解压到临时目录
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name="Ordina",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=cfg["upx_exclude"],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        icon=cfg["icon"],
        version=cfg["version_file"],
    )
else:
    # 单目录：依赖放 _internal/，启动更快，便于排查
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="Ordina",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=cfg["upx_exclude"],
        console=False,
        disable_windowed_traceback=False,
        icon=cfg["icon"],
        version=cfg["version_file"],
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=True,
        upx_exclude=cfg["upx_exclude"],
        name="Ordina",
    )
