# -*- coding: utf-8 -*-
"""
PyInstaller spec 共用配置
=========================
两个 spec（GUI / CLI）都从这里取路径、版本号、排除清单与隐藏导入，
避免同一份配置在两处漂移。
"""

import os
import re

#: 与本项目无关的模块 —— 标准库测试/文档工具 + 常见第三方大包。
#: 目的只有一个：缩小产物体积。排除不存在的模块是无害的。
EXCLUDES = [
    # 标准库中的测试与文档工具
    "unittest", "doctest", "pydoc", "pydoc_data", "lib2to3",
    "test", "tkinter.test", "idlelib", "turtledemo", "turtle",
    # 打包/安装工具链
    "setuptools", "pkg_resources", "pip", "wheel",
    # 常见第三方大包（本项目未使用，防止被间接带入）
    "numpy", "pandas", "matplotlib", "scipy", "PIL", "sklearn",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "notebook", "pytest",
    # 网络 / 邮件 / 数据库（本项目纯本地文件操作，一个都用不到）
    # 注意：urllib 不能排除 —— Python 3.12 的 pathlib 依赖 urllib.parse，
    #      而 PyInstaller 的 pyi_rth_inspect 运行时钩子会导入 inspect → zipfile → pathlib。
    "email", "http", "xml", "smtplib", "imaplib", "poplib",
    "ftplib", "telnetlib", "socketserver", "sqlite3",
    # 调试 / 性能分析
    "pdb", "profile", "cProfile", "timeit", "zoneinfo", "decimal", "curses",
    # 注意：asyncio 不可排除 —— android/adb_bridge.py 依赖它
]

#: 动态 / 条件导入的保底清单（__main__.py 的分流导入、recognizer 的 EXIF 分支等）
HIDDEN_BASE = [
    "ordina",
    "ordina.core", "ordina.core.classifiers", "ordina.core.config",
    "ordina.core.naming", "ordina.core.organizer", "ordina.core.recognizer",
    "ordina.core.archiver", "ordina.core.reporter",
    "ordina.cli", "ordina.cli.main",
    "ordina.android", "ordina.android.adb_bridge", "ordina.android.phone_config",
    "ordina.android.phone_scanner", "ordina.android.phone_organizer",
]

#: 仅 GUI 需要（CLI 版排除后可甩掉整个 tkinter 运行时）
HIDDEN_UI = [
    "ordina.ui", "ordina.ui.app", "ordina.ui.theme", "ordina.ui.widgets",
    "ordina.ui.tabs", "ordina.ui.tabs.base", "ordina.ui.tabs.organize",
    "ordina.ui.tabs.duplicate", "ordina.ui.tabs.analyze",
    "ordina.ui.tabs.rules", "ordina.ui.tabs.logs",
]


def _read_version(root: str) -> str:
    """从 ordina/__init__.py 读取版本号，避免 spec 里硬编码"""
    init_file = os.path.join(root, "ordina", "__init__.py")
    with open(init_file, encoding="utf-8") as fh:
        match = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read())
    return match.group(1) if match else "0.0.0"


def configure(spec_path: str, include_ui: bool = True) -> dict:
    """根据 spec 文件位置推导项目根、版本、图标与各类清单"""
    packaging = os.path.dirname(os.path.abspath(spec_path))
    root = os.path.dirname(packaging)
    icon = os.path.join(root, "assets", "icon.ico")

    hidden = list(HIDDEN_BASE)
    if include_ui:
        hidden += HIDDEN_UI

    excludes = list(EXCLUDES)
    if not include_ui:
        # CLI 不需要图形栈，排除后体积可减半
        excludes += ["tkinter"]

    return {
        "root": root,
        "packaging": packaging,
        "version": _read_version(root),
        "icon": icon if os.path.exists(icon) else None,
        "version_file": os.path.join(packaging, "version_info.py"),
        "hidden": hidden,
        "excludes": excludes,
        "datas": [(icon, "assets")] if os.path.exists(icon) else [],
    }
