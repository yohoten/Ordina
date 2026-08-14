"""
手机文件扫描器
==============
封装 ADB 文件列表能力，提供：
1. 递归目录扫描（支持深度控制）
2. 按扩展名/模式/类型过滤
3. 文件信息提取（大小、日期、权限）
4. 扫描结果缓存
5. 进度报告回调
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Callable, Set, Tuple

from .adb_bridge import AdbBridge, PhoneFileInfo, AdbError

logger = logging.getLogger(__name__)


@dataclass
class ScanProgress:
    """扫描进度信息"""
    current_dir: str = ""
    files_found: int = 0
    dirs_scanned: int = 0
    total_dirs: int = 0
    percent: float = 0.0
    elapsed_seconds: float = 0.0
    message: str = ""


@dataclass
class ScanResult:
    """扫描结果"""
    files: List[PhoneFileInfo] = field(default_factory=list)
    directories: List[PhoneFileInfo] = field(default_factory=list)
    total_size: int = 0
    scanned_dirs: int = 0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def dir_count(self) -> int:
        return len(self.directories)

    @property
    def total_size_formatted(self) -> str:
        """格式化的总大小"""
        return self._format_size(self.total_size)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


class PhoneScanner:
    """
    手机文件扫描器

    支持按目录、扩展名、文件名模式扫描手机文件系统。
    可挂载进度回调用于 UI 展示。

    用法:
        bridge = AdbBridge()
        bridge.select_device()
        scanner = PhoneScanner(bridge)

        # 扫描下载目录
        result = scanner.scan_directory("/sdcard/Download", max_depth=2)

        # 按类型扫描
        apks = scanner.scan_by_extension("/sdcard", [".apk"])
        imgs = scanner.scan_by_extension("/sdcard/DCIM", [".jpg", ".png"])

        # 带进度回调
        def on_progress(p):
            print(f"{p.percent:.0f}% - {p.current_dir}")
        result = scanner.scan_with_progress("/sdcard", callback=on_progress)
    """

    def __init__(self, bridge: AdbBridge):
        """
        Args:
            bridge: 已连接设备的 AdbBridge 实例
        """
        self.bridge = bridge
        self._scan_cache: Dict[str, Tuple[float, ScanResult]] = {}
        self._cache_ttl = 30  # 缓存有效期（秒）

        # 已知应跳过的系统目录
        self.skip_directories: Set[str] = {
            "/sdcard/Android/data",
            "/sdcard/Android/obb",
            "/sdcard/Android/media",
            ".thumbnails",
            ".cache",
            "LOST.DIR",
        }

    # ── 目录扫描 ──────────────────────────────────────────────

    def scan_directory(self, remote_path: str,
                       max_depth: int = 3,
                       include_hidden: bool = False,
                       file_extensions: Optional[List[str]] = None,
                       min_size: int = 0,
                       max_size: int = 0,
                       use_cache: bool = False) -> ScanResult:
        """
        扫描手机目录（递归）

        Args:
            remote_path: 手机目录路径
            max_depth: 最大递归深度 (0=不递归, -1=无限)
            include_hidden: 是否包含隐藏文件
            file_extensions: 仅包含这些扩展名 (None=全部)
            min_size: 最小文件大小 (bytes, 0=不限制)
            max_size: 最大文件大小 (bytes, 0=不限制)
            use_cache: 是否使用缓存

        Returns:
            扫描结果
        """
        remote_path = remote_path.rstrip("/")

        # 检查缓存
        if use_cache:
            cache_key = f"{remote_path}:d{max_depth}:h{include_hidden}"
            if cache_key in self._scan_cache:
                timestamp, result = self._scan_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    logger.debug(f"命中扫描缓存: {cache_key}")
                    return result

        ext_set = set(e.lower() if e.startswith(".") else f".{e}"
                      for e in (file_extensions or []))
        result = ScanResult()
        start_time = time.time()

        try:
            self._scan_recursive(
                remote_path=remote_path,
                current_depth=0,
                max_depth=max_depth,
                include_hidden=include_hidden,
                ext_set=ext_set,
                min_size=min_size,
                max_size=max_size,
                result=result,
            )
        except AdbError as e:
            logger.error(f"扫描中断: {remote_path} - {e}")
            result.errors.append(f"扫描中断: {str(e)}")

        result.elapsed_seconds = time.time() - start_time

        # 写入缓存
        if use_cache:
            cache_key = f"{remote_path}:d{max_depth}:h{include_hidden}"
            self._scan_cache[cache_key] = (time.time(), result)

        return result

    def _scan_recursive(self, remote_path: str, current_depth: int,
                        max_depth: int, include_hidden: bool,
                        ext_set: Set[str], min_size: int, max_size: int,
                        result: ScanResult):
        """递归扫描目录"""
        if max_depth >= 0 and current_depth > max_depth:
            return

        try:
            entries = self.bridge.list_files(remote_path, show_hidden=include_hidden)
        except AdbError as e:
            result.errors.append(f"读取目录失败: {remote_path} - {e}")
            return

        for entry in entries:
            # 跳过系统目录
            if entry.is_dir and self._should_skip(entry.name):
                continue

            if entry.is_dir:
                result.directories.append(entry)
                result.scanned_dirs += 1

                # 递归子目录
                self._scan_recursive(
                    remote_path=entry.path,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    include_hidden=include_hidden,
                    ext_set=ext_set,
                    min_size=min_size,
                    max_size=max_size,
                    result=result,
                )
            else:
                # 文件过滤
                if ext_set and entry.extension not in ext_set:
                    continue
                if min_size > 0 and entry.size < min_size:
                    continue
                if max_size > 0 and entry.size > max_size:
                    continue

                result.files.append(entry)
                result.total_size += entry.size

    def _should_skip(self, dir_name: str) -> bool:
        """判断是否应跳过此目录"""
        return dir_name in self.skip_directories

    # ── 带进度回调的扫描 ──────────────────────────────────────

    def scan_with_progress(self, remote_path: str,
                           max_depth: int = 3,
                           callback: Optional[Callable[[ScanProgress], None]] = None,
                           **kwargs) -> ScanResult:
        """
        带进度回调的扫描

        Args:
            remote_path: 起始目录
            max_depth: 最大深度
            callback: 进度回调函数，接收 ScanProgress 对象
            **kwargs: 传递给 scan_directory 的其他参数

        Returns:
            扫描结果
        """
        # 先快速获取子目录总数（用于进度估算）
        try:
            top_entries = self.bridge.list_files(remote_path)
            total_subdirs = sum(1 for e in top_entries if e.is_dir and not self._should_skip(e.name))
        except AdbError:
            total_subdirs = 0

        # 自定义递归扫描（带进度回调）
        result = ScanResult()
        start_time = time.time()

        progress = ScanProgress(
            current_dir=remote_path,
            total_dirs=total_subdirs,
            message="开始扫描..."
        )

        if callback:
            callback(progress)

        try:
            self._scan_recursive_with_progress(
                remote_path=remote_path,
                current_depth=0,
                max_depth=max_depth,
                include_hidden=kwargs.get("include_hidden", False),
                ext_set=set(),
                min_size=kwargs.get("min_size", 0),
                max_size=kwargs.get("max_size", 0),
                result=result,
                progress=progress,
                callback=callback,
            )
        except AdbError as e:
            logger.error(f"扫描中断: {remote_path} - {e}")
            result.errors.append(f"扫描中断: {str(e)}")

        result.elapsed_seconds = time.time() - start_time

        if callback:
            progress.message = "扫描完成"
            progress.percent = 100.0
            progress.elapsed_seconds = result.elapsed_seconds
            callback(progress)

        return result

    def _scan_recursive_with_progress(self, remote_path, current_depth,
                                      max_depth, include_hidden, ext_set,
                                      min_size, max_size, result,
                                      progress, callback):
        """带进度回调的递归扫描"""
        if max_depth >= 0 and current_depth > max_depth:
            return

        # 更新进度
        progress.current_dir = remote_path
        if callback:
            callback(progress)

        try:
            entries = self.bridge.list_files(remote_path, show_hidden=include_hidden)
        except AdbError as e:
            result.errors.append(f"读取目录失败: {remote_path} - {e}")
            return

        for entry in entries:
            if entry.is_dir and self._should_skip(entry.name):
                continue

            if entry.is_dir:
                result.directories.append(entry)
                result.scanned_dirs += 1
                progress.dirs_scanned += 1

                if total_dirs := progress.total_dirs:
                    progress.percent = min(95.0, (progress.dirs_scanned / total_dirs) * 100)

                self._scan_recursive_with_progress(
                    remote_path=entry.path,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                    include_hidden=include_hidden,
                    ext_set=ext_set,
                    min_size=min_size,
                    max_size=max_size,
                    result=result,
                    progress=progress,
                    callback=callback,
                )
            else:
                if ext_set and entry.extension not in ext_set:
                    continue
                if min_size > 0 and entry.size < min_size:
                    continue
                if max_size > 0 and entry.size > max_size:
                    continue

                result.files.append(entry)
                result.total_size += entry.size
                progress.files_found += 1

    # ── 专项扫描 ──────────────────────────────────────────────

    def scan_by_extension(self, base_path: str,
                          extensions: List[str],
                          max_depth: int = 5) -> ScanResult:
        """
        按文件扩展名扫描

        Args:
            base_path: 起始目录
            extensions: 扩展名列表，如 [".apk", ".jpg"]
            max_depth: 最大深度
        """
        return self.scan_directory(
            base_path,
            max_depth=max_depth,
            file_extensions=extensions,
        )

    def scan_by_pattern(self, base_path: str, pattern: str,
                        file_type: str = "f",
                        max_depth: int = 5,
                        timeout: int = 60) -> ScanResult:
        """
        按文件名模式搜索（使用 find 命令，速度更快）

        Args:
            base_path: 起始目录
            pattern: 文件名通配模式，如 "*.apk"、"IMG_*"
            file_type: "f"=文件 "d"=目录
            max_depth: 最大深度
            timeout: 超时秒数

        Returns:
            扫描结果
        """
        result = ScanResult()
        start_time = time.time()

        try:
            matches = self.bridge.find_files(
                base_path=base_path,
                pattern=pattern,
                file_type=file_type,
                max_depth=max_depth,
                timeout=timeout,
            )

            for m in matches:
                if file_type != "d":
                    # 尝试获取详细信息
                    info = self.bridge.get_file_info(m.path)
                    if info:
                        result.files.append(info)
                        result.total_size += info.size
                    else:
                        result.files.append(m)
                else:
                    result.directories.append(m)
                    result.scanned_dirs += 1

        except AdbError as e:
            result.errors.append(str(e))

        result.elapsed_seconds = time.time() - start_time
        return result

    def find_large_files(self, base_path: str,
                         min_size_mb: int = 50,
                         max_depth: int = 3) -> ScanResult:
        """
        扫描大文件

        Args:
            base_path: 起始目录
            min_size_mb: 最小文件大小 (MB)
            max_depth: 最大深度
        """
        min_bytes = min_size_mb * 1024 * 1024
        return self.scan_directory(
            base_path,
            max_depth=max_depth,
            min_size=min_bytes,
        )

    def find_duplicate_candidates(self, base_path: str,
                                  extensions: Optional[List[str]] = None,
                                  max_depth: int = 3) -> Dict[str, List[PhoneFileInfo]]:
        """
        查找可能的重复文件（按文件名和大小分组）

        Args:
            base_path: 起始目录
            extensions: 关注的扩展名
            max_depth: 最大深度

        Returns:
            {文件名: [相同文件名的文件列表]}
        """
        result = self.scan_directory(
            base_path,
            max_depth=max_depth,
            file_extensions=extensions,
        )

        # 按 (文件名, 大小) 分组
        groups: Dict[str, List[PhoneFileInfo]] = {}
        for f in result.files:
            key = f"{f.name}:{f.size}"
            if key not in groups:
                groups[key] = []
            groups[key].append(f)

        # 只保留有重复的组
        return {k: v for k, v in groups.items() if len(v) > 1}

    # ── 缓存管理 ──────────────────────────────────────────────

    def clear_cache(self):
        """清空扫描缓存"""
        self._scan_cache.clear()

    def set_cache_ttl(self, seconds: int):
        """设置缓存有效期"""
        self._cache_ttl = seconds

    # ── 实用统计 ──────────────────────────────────────────────

    def summarize(self, result: ScanResult) -> Dict:
        """
        生成扫描结果的摘要统计

        Args:
            result: 扫描结果

        Returns:
            统计字典
        """
        ext_count: Dict[str, int] = {}
        ext_size: Dict[str, int] = {}

        for f in result.files:
            ext = f.extension or "(无)"
            ext_count[ext] = ext_count.get(ext, 0) + 1
            ext_size[ext] = ext_size.get(ext, 0) + f.size

        # 按大小降序排列扩展名
        top_extensions = sorted(
            ext_size.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "total_files": result.file_count,
            "total_dirs": result.dir_count,
            "total_size": result.total_size,
            "total_size_formatted": result.total_size_formatted,
            "scanned_dirs": result.scanned_dirs,
            "elapsed_seconds": round(result.elapsed_seconds, 1),
            "errors": len(result.errors),
            "top_extensions": [
                {"ext": ext, "count": ext_count.get(ext, 0), "size": size}
                for ext, size in top_extensions
            ],
        }
