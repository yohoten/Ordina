# -*- coding: utf-8 -*-
"""
PyInstaller spec 共用配置
=========================
GUI spec 从这里取路径、版本号、排除清单、隐藏导入与 UPX 设置，
避免同一份配置在多处漂移。

只打 GUI 一个目标（CLI 打包已移除）：
    onedir  → dist/Ordina/Ordina.exe
    onefile → dist/Ordina.exe
"""

import os
import re

#: 与本项目无关的模块 —— 目的只有一个：缩小产物体积。
#: 排除不存在的模块是无害的，所以这里可以保守地多列一些。
EXCLUDES = [
    # ---- 标准库中的测试与文档工具 ----
    "unittest", "doctest", "pydoc", "pydoc_data", "lib2to3",
    "test", "idlelib", "turtledemo", "turtle",
    # ---- 打包 / 安装工具链 ----
    "setuptools", "pkg_resources", "pip", "wheel", "distutils",
    # ---- 第三方大包 ----
    # 本项目零第三方依赖；列在这里是给构建环境上保险 —— 万一解释器里
    # 装了它们（系统 Python 常常有 numpy / pandas / pillow …），也不会被间接带入。
    "numpy", "pandas", "matplotlib", "scipy", "sklearn", "PIL",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "notebook", "pytest",
    # ---- 网络 / 邮件 / 数据库 ----
    # 本项目是纯本地文件操作，一个都用不到。
    #   · ssl   : asyncio.base_events 里是 try/except ImportError，排除安全（省 ~1MB，含 libssl-3.dll）
    #   · urllib: 绝不能排除 —— Python 3.12 的 pathlib 依赖 urllib.parse，
    #             而 PyInstaller 运行时钩子 pyi_rth_inspect 会走 inspect → zipfile → pathlib。
    "ssl", "email", "http", "xml", "smtplib", "imaplib", "poplib",
    "ftplib", "telnetlib", "socketserver", "sqlite3",
    # ---- 压缩 / 归档后端 ----
    # archiver 只用 shutil.move；zipfile 仅 PyInstaller 运行时钩子用到，
    # 且 zipfile / shutil 里对 bz2、lzma 都是 try/except 的可选导入。
    "bz2", "lzma", "_lzma",
    # ---- 调试 / 性能分析 ----
    "pdb", "profile", "cProfile", "timeit", "zoneinfo", "curses",
    # 注意：asyncio / concurrent / multiprocessing 都不可排除 ——
    #       android/adb_bridge.py 依赖 asyncio，asyncio 又依赖 concurrent.futures。
]

#: 动态 / 条件导入的保底清单（__main__.py 的分流导入、recognizer 的 EXIF 分支等）
HIDDEN_IMPORTS = [
    "ordina",
    "ordina.core", "ordina.core.classifiers", "ordina.core.config",
    "ordina.core.naming", "ordina.core.organizer", "ordina.core.recognizer",
    "ordina.core.archiver", "ordina.core.reporter",
    "ordina.cli", "ordina.cli.main",
    "ordina.android", "ordina.android.adb_bridge", "ordina.android.phone_config",
    "ordina.android.phone_scanner", "ordina.android.phone_organizer",
    "ordina.ui", "ordina.ui.app", "ordina.ui.theme", "ordina.ui.widgets",
    "ordina.ui.tabs", "ordina.ui.tabs.base", "ordina.ui.tabs.organize",
    "ordina.ui.tabs.duplicate", "ordina.ui.tabs.analyze",
    "ordina.ui.tabs.rules", "ordina.ui.tabs.logs",
]

#: 不交给 UPX 压缩的文件（fnmatch 风格，匹配文件名即可）。
#: 这些都是 MSVC 运行时或加载顺序敏感的模块，压缩后偶发启动失败，
#: 而它们本身只有几十 KB，压了也省不了多少 —— 收益远不抵风险。
UPX_EXCLUDE = [
    "vcruntime140.dll",
    "msvcp140.dll",
    "ucrtbase.dll",
    "concrt140.dll",
]


def _read_version(root: str) -> str:
    """从 ordina/__init__.py 读取版本号，避免 spec 里硬编码"""
    init_file = os.path.join(root, "ordina", "__init__.py")
    with open(init_file, encoding="utf-8") as fh:
        match = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read())
    return match.group(1) if match else "0.0.0"


def find_upx(*preferred: str) -> str:
    """
    定位 UPX 可执行文件所在目录，找不到返回空字符串（PyInstaller 会自动关闭压缩）。

    查找顺序：显式传入的目录 → PATH → 常见安装位置。
    """
    candidates = [d for d in preferred if d]
    candidates += [
        r"H:\upx",
        r"C:\upx",
        r"C:\Program Files\upx",
        r"C:\tools\upx",
    ]
    for d in candidates:
        exe = os.path.join(d, "upx.exe")
        if os.path.isfile(exe):
            return d

    # 退而求其次：PATH 里找
    for d in os.environ.get("PATH", "").split(os.pathsep):
        d = d.strip().strip('"')
        if d and os.path.isfile(os.path.join(d, "upx.exe")):
            return d
    return ""


def configure(spec_path: str, extra_excludes=None) -> dict:
    """根据 spec 文件位置推导项目根、版本、图标与各类清单"""
    packaging = os.path.dirname(os.path.abspath(spec_path))
    root = os.path.dirname(packaging)
    icon = os.path.join(root, "assets", "icon.ico")

    excludes = list(EXCLUDES) + list(extra_excludes or [])

    return {
        "root": root,
        "packaging": packaging,
        "version": _read_version(root),
        "icon": icon if os.path.exists(icon) else None,
        "version_file": os.path.join(packaging, "version_info.py"),
        "hidden": list(HIDDEN_IMPORTS),
        "excludes": excludes,
        "upx_exclude": list(UPX_EXCLUDE),
        "datas": [(icon, "assets")] if os.path.exists(icon) else [],
    }
