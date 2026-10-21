"""
安卓手机文件管理支持包
=====================
为 Ordina（归序）提供通过 ADB（Android Debug Bridge）管理手机文件的能力。

模块结构:
- adb_bridge.py:    ADB 连接、设备检测、文件操作（pull/push/list/delete/move）
- phone_config.py:  安卓常见目录映射、文件类型规则、厂商/机型配置
- phone_scanner.py: 手机目录递归扫描、文件信息提取
- phone_organizer.py: 手机文件整理引擎（继承现有 FileOrganizer 设计模式）
"""

__version__ = "1.0.0"
__all__ = [
    "AdbBridge",
    "AdbError",
    "DeviceNotFoundError",
    "AdbNotInstalledError",
    "PhoneScanner",
    "PhoneOrganizer",
    "phone_config",
]

from .adb_bridge import AdbBridge, AdbError, DeviceNotFoundError, AdbNotInstalledError
from . import phone_config
from .phone_scanner import PhoneScanner
from .phone_organizer import PhoneOrganizer
