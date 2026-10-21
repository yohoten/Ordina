"""
ADB 桥接模块 — 通过 Android Debug Bridge 连接和管理手机文件
===========================================================

核心职责:
1. 检测 ADB 环境是否可用
2. 发现和管理连接的安卓设备
3. 执行手机文件系统操作（list/pull/push/delete/move/rename）
4. 获取文件元信息（大小、日期、权限）
5. 错误处理与重试机制

用法:
    bridge = AdbBridge()
    if bridge.detect_devices():
        files = bridge.list_files("/sdcard/Download")
        bridge.pull_file("/sdcard/Download/report.pdf", "./local_copy.pdf")
        bridge.delete_file("/sdcard/Download/temp.tmp")
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Union

logger = logging.getLogger(__name__)

# ── 异常类型 ────────────────────────────────────────────────────


class AdbError(Exception):
    """ADB 操作通用异常"""
    pass


class AdbNotInstalledError(AdbError):
    """ADB 未安装"""
    def __init__(self):
        super().__init__(
            "ADB (Android Debug Bridge) 未找到。\n"
            "请安装 Platform Tools: https://developer.android.com/studio/releases/platform-tools\n"
            "或将 adb.exe 所在目录添加到系统 PATH 环境变量中。"
        )


class DeviceNotFoundError(AdbError):
    """未检测到连接的设备"""
    def __init__(self):
        super().__init__(
            "未检测到已连接的安卓设备。\n"
            "请确保:\n"
            "1. 手机已通过 USB 连接电脑\n"
            "2. 已开启「开发者模式」和「USB 调试」\n"
            "3. 已授权电脑的 USB 调试请求\n"
            "4. 尝试运行: adb devices"
        )


class DeviceOfflineError(AdbError):
    """设备已检测到但处于离线状态"""
    def __init__(self, device_id: str):
        super().__init__(
            f"设备 {device_id} 已检测到但处于离线状态。\n"
            f"请检查 USB 连接或重新插拔。"
        )


class AdbCommandError(AdbError):
    """ADB 命令执行失败"""
    def __init__(self, command: str, return_code: int, stderr: str):
        self.command = command
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(
            f"ADB 命令失败 (code={return_code}): {command}\n{stderr}"
        )


# ── 数据模型 ────────────────────────────────────────────────────


@dataclass
class DeviceInfo:
    """连接的安卓设备信息"""
    id: str                              # 设备序列号
    state: str = "device"                # device / offline / unauthorized
    model: str = ""                      # 设备型号
    manufacturer: str = ""               # 制造商
    android_version: str = ""            # Android 版本
    sdk_version: str = ""                # SDK 版本号
    product_name: str = ""               # 产品名
    battery_level: int = -1              # 电量百分比
    storage_total: int = 0               # 总存储 (bytes)
    storage_used: int = 0                # 已用存储 (bytes)
    is_authorized: bool = True           # 是否已授权


@dataclass
class PhoneFileInfo:
    """手机文件信息"""
    path: str                            # 完整路径
    name: str                            # 文件名
    is_dir: bool = False                 # 是否为目录
    size: int = 0                        # 文件大小 (bytes)
    permissions: str = ""                # Linux 权限字符串 (如 -rw-rw----)
    owner: str = ""                      # 所有者
    group: str = ""                      # 所属组
    modified_time: Optional[datetime] = None  # 修改时间
    extension: str = ""                  # 扩展名 (小写)
    parent_path: str = ""                # 父目录路径


# ═══════════════════════════════════════════════════════════════
# ADB 桥接核心类
# ═══════════════════════════════════════════════════════════════


class AdbBridge:
    """
    ADB 桥接器 — 管理安卓设备连接与文件操作

    所有对外方法均同步执行（内部使用 subprocess 调用 adb）。
    支持多设备管理、超时控制、命令重试。

    用法:
        bridge = AdbBridge()
        bridge.detect_devices()       # 检测设备
        bridge.list_files(path)       # 列出文件
        bridge.pull_file(src, dst)    # 手机→电脑
        bridge.push_file(src, dst)    # 电脑→手机
    """

    # ADB 命令超时（秒）
    DEFAULT_TIMEOUT = 30
    LONG_TIMEOUT = 120  # pull/push 大文件用

    # 常用手机内部存储路径
    COMMON_BASE_PATHS = [
        "/sdcard",
        "/storage/emulated/0",
        "/mnt/sdcard",
        "/data/media/0",
    ]

    def __init__(self, adb_path: Optional[str] = None, device_id: Optional[str] = None):
        """
        Args:
            adb_path: adb 可执行文件路径，None 则自动搜索 PATH
            device_id: 目标设备 ID，None 则在首次操作时自动选择
        """
        self._adb_path: Optional[str] = adb_path
        self._device_id: Optional[str] = device_id
        self._cached_devices: List[DeviceInfo] = []

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def adb_path(self) -> str:
        """获取 ADB 可执行文件路径"""
        if self._adb_path is None:
            self._adb_path = self._find_adb()
        return self._adb_path

    @property
    def device_id(self) -> Optional[str]:
        return self._device_id

    @device_id.setter
    def device_id(self, value: str):
        self._device_id = value

    # ── ADB 环境检测 ──────────────────────────────────────────

    @staticmethod
    def _find_adb() -> str:
        """
        在系统中查找 adb 可执行文件

        搜索顺序:
        1. PATH 环境变量
        2. 常见安装路径 (Platform Tools)
        3. 当前目录

        Returns:
            adb 可执行文件的完整路径

        Raises:
            AdbNotInstalledError: 未找到 adb
        """
        # 检查 PATH
        adb_name = "adb.exe" if sys.platform == "win32" else "adb"
        adb_path = shutil_which(adb_name)
        if adb_path:
            return adb_path

        # 常见安装路径
        common_paths = [
            # Windows 平台工具默认路径
            r"C:\Program Files\Android\android-sdk\platform-tools\adb.exe",
            r"C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Android\Sdk\platform-tools\adb.exe",
            # macOS / Linux
            "/usr/local/bin/adb",
            "/usr/bin/adb",
            "~/Library/Android/sdk/platform-tools/adb",
            # 当前目录
            os.path.join(os.getcwd(), adb_name),
        ]

        userprofile = os.environ.get("USERPROFILE", "")
        for path in common_paths:
            path = path.replace("%USERNAME%", os.environ.get("USERNAME", ""))
            path = path.replace("~", os.path.expanduser("~"))
            if os.path.isfile(path):
                return path

        raise AdbNotInstalledError()

    def is_available(self) -> bool:
        """检查 ADB 环境是否可用"""
        try:
            result = self._raw_adb("--version", timeout=10)
            return result.returncode == 0
        except (AdbNotInstalledError, FileNotFoundError):
            return False

    def get_version(self) -> str:
        """获取 ADB 版本信息"""
        result = self._raw_adb("--version", timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        return ""

    # ── 设备发现与管理 ────────────────────────────────────────

    def detect_devices(self, force_refresh: bool = False) -> List[DeviceInfo]:
        """
        检测所有已连接的安卓设备

        Args:
            force_refresh: 强制刷新设备列表（跳过缓存）

        Returns:
            设备信息列表
        """
        if self._cached_devices and not force_refresh:
            return self._cached_devices

        result = self._raw_adb("devices -l", timeout=15)
        if result.returncode != 0:
            logger.warning(f"ADB devices 命令失败: {result.stderr}")
            return []

        devices = self._parse_devices_output(result.stdout)
        self._cached_devices = devices
        return devices

    def _parse_devices_output(self, output: str) -> List[DeviceInfo]:
        """
        解析 `adb devices -l` 输出

        输出格式:
            List of devices attached
            emulator-5554   device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64xa ...
            0123456789ABCDEF device usb:1-1 product:SM-S9280 model:SM-S9280 device:zulu ...
        """
        devices = []
        lines = output.strip().splitlines()

        for line in lines:
            # 跳过标题行和空行
            if line.startswith("List") or not line.strip():
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            device_id = parts[0]
            state = parts[1]

            if state == "unauthorized":
                devices.append(DeviceInfo(id=device_id, state=state, is_authorized=False))
                continue

            # 解析 -l 额外信息
            info = DeviceInfo(id=device_id, state=state)
            for part in parts[2:]:
                if ":" in part:
                    key, _, value = part.partition(":")
                    if key == "product":
                        info.product_name = value
                    elif key == "model":
                        info.model = value
                    elif key == "device":
                        info.manufacturer = value  # device 字段通常为代号

            # 尝试获取更多设备信息
            if state == "device":
                self._enrich_device_info(info)

            devices.append(info)

        return devices

    def _enrich_device_info(self, info: DeviceInfo):
        """通过 ADB shell 获取设备详细信息"""
        try:
            # Android 版本
            build_version = self.shell("getprop ro.build.version.release", timeout=10)
            if build_version:
                info.android_version = build_version.strip()

            # SDK 版本
            sdk = self.shell("getprop ro.build.version.sdk", timeout=10)
            if sdk:
                info.sdk_version = sdk.strip()

            # 获取型号（如未从 -l 获取到）
            if not info.model:
                model = self.shell("getprop ro.product.model", timeout=10)
                if model:
                    info.model = model.strip()

            # 获取制造商
            if not info.manufacturer:
                mfr = self.shell("getprop ro.product.manufacturer", timeout=10)
                if mfr:
                    info.manufacturer = mfr.strip()

            # 电量
            battery = self.shell("dumpsys battery | grep level", timeout=10)
            if battery:
                match = re.search(r"level:\s*(\d+)", battery)
                if match:
                    info.battery_level = int(match.group(1))

            # 存储信息
            storage = self.shell("df /sdcard", timeout=10)
            if storage:
                match = re.search(
                    r"/sdcard\s+(\d+)\s+(\d+)\s+(\d+)",
                    storage.replace(",", "")
                )
                if match:
                    info.storage_total = int(match.group(2)) * 1024  # 1K-blocks → bytes
                    info.storage_used = int(match.group(3)) * 1024

        except AdbError as e:
            logger.debug(f"获取设备详细信息失败: {e}")

    def select_device(self, device_id: Optional[str] = None) -> DeviceInfo:
        """
        选择目标设备

        Args:
            device_id: 设备 ID，None 则自动选择第一个可用设备

        Returns:
            选中的设备信息

        Raises:
            DeviceNotFoundError: 无可用设备
            DeviceOfflineError: 设备离线
        """
        if device_id:
            self._device_id = device_id
        else:
            devices = self.detect_devices(force_refresh=True)
            available = [d for d in devices if d.state == "device" and d.is_authorized]

            if not available:
                offline = [d for d in devices if d.state == "offline"]
                unauthorized = [d for d in devices if not d.is_authorized]

                if offline:
                    raise DeviceOfflineError(offline[0].id)
                elif unauthorized:
                    raise AdbError("设备未授权，请在手机上允许 USB 调试。")
                else:
                    raise DeviceNotFoundError()

            self._device_id = available[0].id
            logger.info(f"已选择设备: {available[0].model or available[0].id}")

        # 返回设备信息
        for d in self._cached_devices:
            if d.id == self._device_id:
                return d
        return DeviceInfo(id=self._device_id)

    # ── ADB 命令执行 ──────────────────────────────────────────

    def _raw_adb(self, command: str, timeout: int = DEFAULT_TIMEOUT,
                 device_specific: bool = False) -> subprocess.CompletedProcess:
        """
        执行原始 ADB 命令（低层级，不添加 -s device_id）

        Args:
            command: ADB 命令参数
            timeout: 超时秒数
            device_specific: 是否自动添加 -s device_id
        """
        cmd = [self.adb_path]

        if device_specific and self._device_id:
            cmd.extend(["-s", self._device_id])

        # Windows cmd.exe 兼容：将命令字符串拆分为参数
        # ADB 支持将整个 shell 命令作为单个参数传入
        cmd.extend(command.split())

        logger.debug(f"ADB cmd: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
            )
            return result
        except subprocess.TimeoutExpired:
            raise AdbError(f"ADB 命令超时 ({timeout}s): {command}")
        except FileNotFoundError:
            raise AdbNotInstalledError()
        except OSError as e:
            raise AdbError(f"ADB 执行失败: {e}")

    def _adb(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        在目标设备上执行 ADB 命令（自动添加 -s device_id）

        Returns:
            命令标准输出

        Raises:
            DeviceNotFoundError: 未指定设备或无可用设备
        """
        if not self._device_id:
            self.select_device()

        result = self._raw_adb(command, timeout=timeout, device_specific=True)

        if result.returncode != 0:
            raise AdbCommandError(
                command, result.returncode, result.stderr.strip()
            )

        return result.stdout

    def shell(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        在设备上执行 shell 命令

        Args:
            command: 要执行的 shell 命令
            timeout: 超时秒数

        Returns:
            命令输出

        示例:
            bridge.shell("ls -la /sdcard/Download")
            bridge.shell("find /sdcard -name '*.apk'")
        """
        return self._adb(f"shell {command}", timeout=timeout)

    # ── 文件系统操作 ──────────────────────────────────────────

    def list_files(self, remote_path: str = "/sdcard",
                   show_hidden: bool = False) -> List[PhoneFileInfo]:
        """
        列出手机目录下的文件

        Args:
            remote_path: 手机上的目录路径
            show_hidden: 是否包含隐藏文件

        Returns:
            文件信息列表

        使用 `ls -la` 获取详细信息，解析 Linux 风格的列表输出。
        """
        # 先规范化路径
        remote_path = self._normalize_path(remote_path)

        cmd = f"ls -la {remote_path}"
        try:
            output = self.shell(cmd, timeout=15)
        except AdbCommandError as e:
            if "No such file or directory" in e.stderr:
                logger.warning(f"目录不存在: {remote_path}")
                return []
            raise

        files = []
        lines = output.strip().splitlines()

        for line in lines:
            if not line.strip():
                continue

            file_info = self._parse_ls_line(line, remote_path)
            if file_info is None:
                continue

            # 过滤 . 和 ..
            if file_info.name in (".", ".."):
                continue

            # 隐藏文件过滤
            if not show_hidden and file_info.name.startswith("."):
                continue

            files.append(file_info)

        return files

    def _parse_ls_line(self, line: str, parent_path: str) -> Optional[PhoneFileInfo]:
        """
        解析 `ls -la` 的一行输出

        格式: -rw-rw---- 1 u0_a123 u0_a123 12345 2024-01-15 10:30 filename.ext
        或:  drwxrwx--x 1 u0_a123 u0_a123 4096 2024-01-15 10:30 dirname
        """
        # 标准 ls -la 格式
        # 权限(10) + 硬链接数 + 所有者 + 组 + 大小 + 日期(2部分) + 文件名
        pattern = (
            r"^([drwxlst\-]{10})\s+"       # 权限位
            r"(\d+)\s+"                     # 硬链接数
            r"(\S+)\s+"                     # 所有者
            r"(\S+)\s+"                     # 组
            r"(\d+)\s+"                     # 大小 (bytes)
            r"(\d{4}[-/]\d{2}[-/]\d{2})"   # 日期 (YYYY-MM-DD)
            r"\s+"                         # 空格
            r"(\d{2}:\d{2})\s+"             # 时间 (HH:MM)
            r"(.+)$"                        # 文件名（可能包含空格）
        )

        match = re.match(pattern, line)
        if not match:
            # 尝试另一种格式（某些旧设备）
            # -rwxr-xr-x root root 12345 2024-01-15 10:30 filename
            pattern2 = (
                r"^([drwxlst\-]{10})\s+"
                r"(\S+)\s+"               # 无硬链接数
                r"(\S+)\s+"               # 所有者
                r"(\S+)\s+"               # 组
                r"(\d+)\s+"
                r"(\d{4}[-/]\d{2}[-/]\d{2})\s+"
                r"(\d{2}:\d{2})\s+"
                r"(.+)$"
            )
            match = re.match(pattern2, line)

        if not match:
            logger.debug(f"无法解析 ls 行: {line}")
            return None

        groups = match.groups()
        perms = groups[0]
        name = groups[-1].strip()
        is_dir = perms.startswith("d")

        try:
            size = int(groups[4]) if len(groups) >= 8 else 0
        except ValueError:
            size = 0

        date_str = groups[-3] if len(groups) >= 8 else ""
        time_str = groups[-2] if len(groups) >= 8 else ""

        modified_time = None
        if date_str:
            try:
                modified_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                pass

        parent = parent_path.rstrip("/")

        return PhoneFileInfo(
            path=f"{parent}/{name}",
            name=name,
            is_dir=is_dir,
            size=size,
            permissions=perms,
            owner=groups[2] if len(groups) >= 8 else "",
            group=groups[3] if len(groups) >= 8 else "",
            modified_time=modified_time,
            extension=Path(name).suffix.lower() if not is_dir else "",
            parent_path=parent,
        )

    def file_exists(self, remote_path: str) -> bool:
        """
        检查手机上的文件或目录是否存在

        Args:
            remote_path: 手机路径
        """
        remote_path = self._normalize_path(remote_path)
        try:
            self.shell(f"test -e {remote_path} && echo 1 || echo 0", timeout=10)
            # 另一种方式
            result = self.shell(f"[ -e '{remote_path}' ] && echo 'EXISTS' || echo 'NOT_FOUND'", timeout=10)
            return "EXISTS" in result
        except AdbError:
            return False

    def get_file_info(self, remote_path: str) -> Optional[PhoneFileInfo]:
        """
        获取单个文件的详细信息

        Args:
            remote_path: 手机路径
        """
        remote_path = self._normalize_path(remote_path)
        parent = str(Path(remote_path).parent).replace("\\", "/")

        try:
            output = self.shell(f"ls -la '{remote_path}' 2>/dev/null", timeout=10)
            if not output.strip():
                return None

            # 取最后一行（排除 total N）
            lines = [l for l in output.strip().splitlines() if l.strip()]
            for line in lines:
                if line.startswith("total"):
                    continue
                return self._parse_ls_line(line, parent)
            return None
        except AdbError:
            return None

    # ── 文件传输 ──────────────────────────────────────────────

    def pull_file(self, remote_path: str, local_path: Union[str, Path],
                  timeout: Optional[int] = None) -> Path:
        """
        从手机拉取文件到电脑

        Args:
            remote_path: 手机上的文件路径
            local_path: 本地保存路径（文件或目录）
            timeout: 超时秒数，默认 120s

        Returns:
            本地保存的完整文件路径

        Raises:
            AdbError: 拉取失败
        """
        remote_path = self._normalize_path(remote_path)
        local_path = Path(local_path)

        # 如果本地路径是目录，保留原文件名
        if local_path.is_dir():
            local_path = local_path / Path(remote_path).name

        # 确保父目录存在
        local_path.parent.mkdir(parents=True, exist_ok=True)

        t = timeout or self.LONG_TIMEOUT
        try:
            output = self._adb(f"pull '{remote_path}' '{local_path}'", timeout=t)
            logger.info(f"拉取完成: {remote_path} → {local_path}")
            return local_path
        except AdbCommandError as e:
            raise AdbError(
                f"从手机拉取文件失败: {remote_path}\n"
                f"目标: {local_path}\n{e.stderr}"
            )

    def pull_directory(self, remote_dir: str, local_dir: Union[str, Path],
                       timeout: Optional[int] = None) -> Path:
        """
        从手机拉取整个目录到电脑

        Args:
            remote_dir: 手机上的目录路径
            local_dir: 本地保存目录
            timeout: 超时秒数
        """
        remote_dir = self._normalize_path(remote_dir)
        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        t = timeout or self.LONG_TIMEOUT * 2
        try:
            self._adb(f"pull '{remote_dir}/' '{local_dir}'", timeout=t)
            return local_dir
        except AdbCommandError as e:
            raise AdbError(
                f"从手机拉取目录失败: {remote_dir}\n"
                f"目标: {local_dir}\n{e.stderr}"
            )

    def push_file(self, local_path: Union[str, Path], remote_path: str,
                  timeout: Optional[int] = None) -> str:
        """
        从电脑推送文件到手机

        Args:
            local_path: 本地文件路径
            remote_path: 手机目标路径
            timeout: 超时秒数

        Returns:
            手机上的目标路径
        """
        local_path = Path(local_path)
        remote_path = self._normalize_path(remote_path)

        if not local_path.exists():
            raise FileNotFoundError(f"本地文件不存在: {local_path}")

        t = timeout or self.LONG_TIMEOUT
        try:
            self._adb(f"push '{local_path}' '{remote_path}'", timeout=t)
            logger.info(f"推送完成: {local_path} → {remote_path}")
            return remote_path
        except AdbCommandError as e:
            raise AdbError(
                f"推送文件到手机失败: {local_path}\n"
                f"目标: {remote_path}\n{e.stderr}"
            )

    # ── 文件操作 ──────────────────────────────────────────────

    def delete_file(self, remote_path: str) -> bool:
        """
        删除手机上的文件

        Args:
            remote_path: 手机文件路径

        Returns:
            是否成功删除
        """
        remote_path = self._normalize_path(remote_path)
        try:
            self.shell(f"rm '{remote_path}'", timeout=15)
            logger.info(f"已删除手机文件: {remote_path}")
            return True
        except AdbCommandError as e:
            logger.error(f"删除手机文件失败: {remote_path} - {e}")
            return False

    def delete_directory(self, remote_path: str, recursive: bool = True) -> bool:
        """
        删除手机上的目录

        Args:
            remote_path: 手机目录路径
            recursive: 是否递归删除
        """
        remote_path = self._normalize_path(remote_path)
        flag = "-rf" if recursive else "-d"
        try:
            self.shell(f"rm {flag} '{remote_path}'", timeout=15)
            logger.info(f"已删除手机目录: {remote_path}")
            return True
        except AdbCommandError as e:
            logger.error(f"删除手机目录失败: {remote_path} - {e}")
            return False

    def move_file(self, source_path: str, target_path: str) -> bool:
        """
        在手机上移动/重命名文件

        Args:
            source_path: 源路径
            target_path: 目标路径
        """
        source_path = self._normalize_path(source_path)
        target_path = self._normalize_path(target_path)

        # 确保目标父目录存在
        parent = str(Path(target_path).parent).replace("\\", "/")
        self.ensure_dir(parent)

        try:
            self.shell(f"mv '{source_path}' '{target_path}'", timeout=15)
            logger.info(f"移动成功: {source_path} → {target_path}")
            return True
        except AdbCommandError as e:
            logger.error(f"移动文件失败: {source_path} → {target_path} - {e}")
            return False

    def copy_file(self, source_path: str, target_path: str) -> bool:
        """
        在手机上复制文件

        Args:
            source_path: 源路径
            target_path: 目标路径
        """
        source_path = self._normalize_path(source_path)
        target_path = self._normalize_path(target_path)

        parent = str(Path(target_path).parent).replace("\\", "/")
        self.ensure_dir(parent)

        try:
            self.shell(f"cp '{source_path}' '{target_path}'", timeout=15)
            logger.info(f"复制成功: {source_path} → {target_path}")
            return True
        except AdbCommandError as e:
            logger.error(f"复制文件失败: {source_path} → {target_path} - {e}")
            return False

    def ensure_dir(self, remote_path: str) -> bool:
        """
        确保手机上的目录存在（不存在则创建）

        Args:
            remote_path: 目录路径
        """
        remote_path = self._normalize_path(remote_path)
        try:
            self.shell(f"mkdir -p '{remote_path}'", timeout=10)
            return True
        except AdbCommandError:
            return False

    # ── 搜索与统计 ────────────────────────────────────────────

    def find_files(self, base_path: str, pattern: str = "",
                   file_type: Optional[str] = None,
                   max_depth: int = 5,
                   timeout: int = 30) -> List[PhoneFileInfo]:
        """
        在手机目录中搜索文件（使用 find 命令）

        Args:
            base_path: 搜索起始目录
            pattern: 文件名模式（支持通配符 * ?）
            file_type: 文件类型过滤 ("f"=文件, "d"=目录, None=全部)
            max_depth: 最大递归深度
            timeout: 超时秒数

        Returns:
            匹配的文件列表
        """
        base_path = self._normalize_path(base_path)

        # 构建 find 命令
        cmd_parts = [f"find '{base_path}'"]

        # 最大深度
        if max_depth > 0:
            cmd_parts.append(f"-maxdepth {max_depth}")

        # 文件类型
        if file_type == "f":
            cmd_parts.append("-type f")
        elif file_type == "d":
            cmd_parts.append("-type d")

        # 名称模式
        if pattern:
            cmd_parts.append(f"-name '{pattern}'")

        cmd = " ".join(cmd_parts)

        try:
            output = self.shell(cmd, timeout=timeout)
            paths = [p.strip() for p in output.strip().splitlines() if p.strip()]

            files = []
            for p in paths:
                files.append(PhoneFileInfo(
                    path=p,
                    name=Path(p).name,
                    is_dir=False,  # find 结果不包含类型信息
                    parent_path=str(Path(p).parent).replace("\\", "/"),
                    extension=Path(p).suffix.lower(),
                ))
            return files
        except AdbCommandError as e:
            logger.warning(f"搜索文件失败: {base_path} - {e}")
            return []

    def get_storage_info(self) -> Dict[str, object]:
        """
        获取手机存储概览信息

        Returns:
            {
                "internal_total": int,      # 内部存储总大小 (bytes)
                "internal_used": int,       # 内部存储已用 (bytes)
                "internal_free": int,       # 内部存储可用 (bytes)
                "sdcard_available": bool,   # 是否有外置 SD 卡
                "sdcard_path": str,         # SD 卡路径
                "download_size": int,       # 下载目录大小
                "dcim_size": int,           # 相册目录大小
            }
        """
        info = {
            "internal_total": 0,
            "internal_used": 0,
            "internal_free": 0,
            "sdcard_available": False,
            "sdcard_path": "",
            "download_size": 0,
            "dcim_size": 0,
        }

        try:
            # 内部存储
            df_out = self.shell("df /sdcard", timeout=10)
            # 解析 df 输出
            match = re.search(
                r"/sdcard\s+(\d+)\s+(\d+)\s+(\d+)",
                df_out.replace(",", "")
            )
            if match:
                blocks_1k = int(match.group(1))
                used_k = int(match.group(2))
                avail_k = int(match.group(3))
                info["internal_total"] = blocks_1k * 1024
                info["internal_used"] = used_k * 1024
                info["internal_free"] = avail_k * 1024

            # 检查外置 SD 卡
            sdcard = self.shell(
                "ls -d /storage/*/ 2>/dev/null | grep -v emulated || echo ''",
                timeout=10
            )
            if sdcard.strip():
                paths = [p.strip() for p in sdcard.strip().splitlines() if p.strip()]
                internal_paths = ["/storage/emulated/", "/storage/self/"]
                for p in paths:
                    if not any(p.startswith(ip) for ip in internal_paths):
                        info["sdcard_available"] = True
                        info["sdcard_path"] = p.rstrip("/")
                        break

            # 下载目录大小
            du_out = self.shell("du -sb /sdcard/Download 2>/dev/null || echo '0'", timeout=10)
            match = re.search(r"(\d+)", du_out)
            if match:
                info["download_size"] = int(match.group(1))

            # DCIM 大小
            du_out = self.shell("du -sb /sdcard/DCIM 2>/dev/null || echo '0'", timeout=10)
            match = re.search(r"(\d+)", du_out)
            if match:
                info["dcim_size"] = int(match.group(1))

        except AdbError as e:
            logger.warning(f"获取存储信息失败: {e}")

        return info

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def _normalize_path(path: str) -> str:
        """规范化手机路径（统一使用正斜杠，去除尾部斜杠）"""
        path = path.replace("\\", "/")
        path = path.rstrip("/")
        return path if path else "/"

    def reconnect(self) -> bool:
        """重新连接 USB 设备"""
        try:
            self._raw_adb("reconnect device", timeout=15)
            time.sleep(2)
            self.detect_devices(force_refresh=True)
            return True
        except AdbError:
            return False

    def kill_server(self):
        """停止 ADB 服务"""
        self._raw_adb("kill-server", timeout=10)

    def start_server(self):
        """启动 ADB 服务"""
        self._raw_adb("start-server", timeout=15)

    def restart_server(self):
        """重启 ADB 服务"""
        self.kill_server()
        time.sleep(1)
        self.start_server()
        time.sleep(2)

    def wait_for_device(self, timeout_seconds: int = 30) -> bool:
        """
        等待设备连接

        Args:
            timeout_seconds: 最大等待秒数

        Returns:
            是否检测到设备
        """
        start = time.time()
        while time.time() - start < timeout_seconds:
            devices = self.detect_devices(force_refresh=True)
            available = [d for d in devices if d.state == "device"]
            if available:
                self._device_id = available[0].id
                return True
            time.sleep(2)
        return False

    def __repr__(self) -> str:
        if self._device_id:
            return f"AdbBridge(device={self._device_id})"
        return f"AdbBridge(devices={len(self._cached_devices)})"


# ── 兼容 shutil.which ──────────────────────────────────────────


def shutil_which(cmd: str) -> Optional[str]:
    """跨平台查找可执行文件"""
    try:
        import shutil
        return shutil.which(cmd)
    except Exception:
        pass

    # 降级方案：遍历 PATH
    path_env = os.environ.get("PATH", "")
    for p in path_env.split(os.pathsep):
        full = os.path.join(p.strip('"'), cmd)
        if os.path.isfile(full):
            return full
    return None
