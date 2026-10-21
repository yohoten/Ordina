"""
手机文件整理引擎
================
继承现有 FileOrganizer 的设计模式，通过 ADB 在手机上完成文件整理。

核心能力:
1. 手机文件分类（复用现有分类器的关键词/正则逻辑）
2. 手机端文件移动（按分类创建目录并移动）
3. 手机文件清理（临时文件、空目录、重复文件）
4. 手机→电脑备份（将手机文件拉取到电脑并按规则整理）
5. 统计报告生成

用法:
    bridge = AdbBridge()
    bridge.select_device()
    organizer = PhoneOrganizer(bridge, mode="purpose")
    organizer.organize("/sdcard/Download", dry_run=True)
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Union, Callable

from ..core.classifiers import BaseClassifier, PurposeClassifier, create_classifier
from ..core.naming import NameNormalizer
from ..core.reporter import Reporter

from .adb_bridge import AdbBridge, PhoneFileInfo, AdbError, DeviceNotFoundError
from .phone_scanner import PhoneScanner, ScanResult
from .phone_config import (
    PHONE_DIRECTORIES,
    PHONE_FILE_PATTERNS,
    get_app_category,
    match_phone_pattern,
    classify_phone_size,
)

logger = logging.getLogger(__name__)


class PhoneOrganizer:
    """
    手机文件整理引擎

    设计思路:
    - 不直接继承 FileOrganizer（本地FS vs ADB 差异太大）
    - 但复用相同的分类器、规范化器、报告器
    - 保持 CLI 接口风格一致

    用法:
        organizer = PhoneOrganizer(adb_bridge)
        organizer.organize("/sdcard/Download")
        organizer.backup_to_pc("/sdcard/DCIM/Camera", "D:/phone_backup")
    """

    def __init__(self,
                 bridge: AdbBridge,
                 mode: str = "purpose",
                 classifier: Optional[BaseClassifier] = None):
        """
        Args:
            bridge: 已连接设备的 AdbBridge 实例
            mode: 分类模式 "extension" | "purpose"
            classifier: 自定义分类器，None 则自动创建
        """
        self.bridge = bridge
        self.mode = mode

        # 分类器 — 复用现有逻辑
        if classifier:
            self.classifier = classifier
        else:
            self.classifier = create_classifier(mode)

        # 辅助模块
        self.scanner = PhoneScanner(bridge)
        self.normalizer = NameNormalizer()

        # 统计
        self.stats = self._init_stats()

    @staticmethod
    def _init_stats() -> Dict:
        return {
            "scanned": 0,
            "moved": 0,
            "deleted": 0,
            "renamed": 0,
            "errors": 0,
            "skipped": 0,
            "backed_up": 0,
        }

    # ── 文件分类（适配手机）───────────────────────────────────

    def classify_phone_file(self, file_info: PhoneFileInfo) -> str:
        """
        对手机文件进行分类

        增强策略:
        1. 先尝试手机专用模式匹配（微信/QQ/相机等）
        2. 回退到现有分类器的关键词/扩展名逻辑
        3. 最终默认分类

        Args:
            file_info: 手机文件信息

        Returns:
            分类名（如 "05_相册" 或 "文档"）
        """
        filename = file_info.name
        filepath_str = file_info.path  # 用于分类器（仅文件名会用到）

        # 1. 手机专用模式匹配（针对手机生成文件的命名模式）
        phone_category = match_phone_pattern(filename)
        if phone_category:
            return phone_category

        # 2. 尝试按 App 来源分类
        app_source = get_app_category(filename)
        if app_source:
            # 将 App 来源映射到用途分类
            app_to_category = {
                "相机拍摄": "05_相册",
                "截图": "05_相册",
                "屏幕录制": "04_视频娱乐",
                "微信": "03_参考资料",
                "QQ": "03_参考资料",
                "钉钉": "01_工作目录",
                "浏览器下载": "03_参考资料",
            }
            if app_source in app_to_category:
                return app_to_category[app_source]

        # 3. 回退到现有分类器
        from pathlib import Path as P
        fake_path = P(filepath_str)
        try:
            return self.classifier.classify(fake_path)
        except Exception:
            pass

        # 4. 默认分类
        return "03_参考资料"

    def _classify_path(self, file_info: PhoneFileInfo) -> str:
        """获取分类目录名（带数字前缀）"""
        category = self.classify_phone_file(file_info)

        # 尝试添加数字前缀
        if hasattr(self.classifier, "get_prefix"):
            try:
                prefix = self.classifier.get_prefix(category)
                if prefix:
                    return f"{prefix}_{category}"
            except Exception:
                pass

        return category

    # ── 手机端文件整理 ────────────────────────────────────────

    def organize(self,
                 remote_path: str = "/sdcard/Download",
                 dry_run: bool = True,
                 max_depth: int = 0,
                 use_date_grouping: bool = False,
                 add_date_suffix: bool = False,
                 progress_callback: Optional[Callable[[str], None]] = None) -> Dict:
        """
        整理手机目录

        流程:
        1. 扫描目标目录
        2. 对每个文件进行分类
        3. 在目标目录内创建分类子目录
        4. 移动文件到对应分类目录

        Args:
            remote_path: 手机上的目标目录
            dry_run: 预览模式（不实际移动）
            max_depth: 扫描深度 (0=仅当前目录)
            use_date_grouping: 按日期分组（YYYY-MM 子目录）
            add_date_suffix: 文件名添加日期后缀
            progress_callback: 进度回调

        Returns:
            整理结果统计
        """
        self.stats = self._init_stats()
        remote_path = remote_path.rstrip("/")

        def log(msg: str):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)

        log(f"{'='*50}")
        log(f"📱 手机文件整理: {remote_path}")
        log(f"   模式: {'预览' if dry_run else '执行'}")
        log(f"{'='*50}")

        # Step 1: 扫描
        log("\n[Step 1] 扫描目录...")
        scan_result = self.scanner.scan_directory(
            remote_path,
            max_depth=max_depth,
            include_hidden=False,
        )

        if not scan_result.files:
            log("   [OK] 目录为空或不存在")
            return {"status": "empty", "stats": self.stats}

        log(f"   找到 {scan_result.file_count} 个文件")
        self.stats["scanned"] = scan_result.file_count

        # Step 2: 分类 + 移动
        log("\n[Step 2] 分类整理...")
        moved_files = []
        category_counts: Dict[str, int] = {}

        for file_info in scan_result.files:
            try:
                category = self._classify_path(file_info)
                category_counts[category] = category_counts.get(category, 0) + 1

                # 构建目标路径
                target_dir = f"{remote_path}/{category}"
                if use_date_grouping and file_info.modified_time:
                    month_str = file_info.modified_time.strftime("%Y-%m")
                    target_dir = f"{target_dir}/{month_str}"

                # 处理文件名（按命名规则：日期后缀 + 安全清洗）
                target_name = file_info.name
                if add_date_suffix:
                    try:
                        target_name = self.normalizer.add_date_suffix(
                            Path(file_info.name), date=file_info.modified_time
                        )
                    except Exception:
                        stem, ext = os.path.splitext(file_info.name)
                        date_str = (file_info.modified_time or datetime.now()).strftime("%Y%m%d")
                        target_name = f"{stem}_{date_str}{ext}"

                target_path = f"{target_dir}/{target_name}"

                # 冲突处理：语义化 _v2 / _v3（与 PC 端保持一致）
                if target_path != file_info.path and self._phone_file_exists(target_path):
                    stem, ext = os.path.splitext(target_name)
                    pattern = self.normalizer.rules.conflict_pattern
                    for n in range(2, 100):
                        candidate = f"{target_dir}/{stem}{pattern.format(n=n)}{ext}"
                        if not self._phone_file_exists(candidate):
                            target_path = candidate
                            break

                # 执行移动
                if not dry_run:
                    self.bridge.ensure_dir(target_dir)
                    success = self.bridge.move_file(file_info.path, target_path)
                    if success:
                        self.stats["moved"] += 1
                        moved_files.append((file_info.path, target_path))
                        log(f"   [OK] {file_info.name} → {category}/")
                    else:
                        self.stats["errors"] += 1
                        log(f"   [ERR] {file_info.name} 移动失败")
                else:
                    self.stats["moved"] += 1
                    moved_files.append((file_info.path, target_path))

            except Exception as e:
                self.stats["errors"] += 1
                log(f"   [ERR] {file_info.name}: {e}")

        # 打印统计
        log(f"\n{'='*50}")
        log(f"📊 整理完成 ({'预览' if dry_run else '执行'}模式)")
        log(f"{'='*50}")
        log(f"   扫描文件: {self.stats['scanned']}")
        log(f"   移动文件: {self.stats['moved']}")
        log(f"   错误:     {self.stats['errors']}")

        if category_counts:
            log("\n   分类分布:")
            for cat, count in sorted(category_counts.items()):
                log(f"     {cat}: {count} 个文件")

        return {
            "status": "success" if self.stats["errors"] == 0 else "partial",
            "stats": self.stats,
            "moved_files": moved_files,
            "category_distribution": category_counts,
            "dry_run": dry_run,
        }

    def _phone_file_exists(self, remote_path: str) -> bool:
        """检查手机路径是否存在"""
        try:
            return self.bridge.file_exists(remote_path)
        except AdbError:
            return False

    # ── 手机→电脑备份 ─────────────────────────────────────────

    def backup_to_pc(self,
                     remote_source: str,
                     local_target: Union[str, Path],
                     organize_after_backup: bool = True,
                     dry_run: bool = True,
                     include_subdirs: bool = False,
                     file_extensions: Optional[List[str]] = None) -> Dict:
        """
        将手机文件备份到电脑，并可选择在电脑上整理

        两步操作:
        1. 从手机拉取文件到电脑临时目录
        2. （可选）用 PC 版 FileOrganizer 对备份目录整理

        Args:
            remote_source: 手机源目录
            local_target: 电脑目标目录
            organize_after_backup: 是否在备份后整理
            dry_run: 预览模式
            include_subdirs: 是否包含子目录
            file_extensions: 仅备份这些类型

        Returns:
            备份结果
        """
        local_target = Path(local_target)
        result = {
            "remote_source": remote_source,
            "local_target": str(local_target),
            "pulled_files": [],
            "organized": False,
            "errors": [],
            "dry_run": dry_run,
        }

        # Step 1: 扫描
        max_depth = -1 if include_subdirs else 0
        scan_result = self.scanner.scan_directory(
            remote_source,
            max_depth=max_depth,
            file_extensions=file_extensions,
        )

        if not scan_result.files and not include_subdirs:
            # 尝试直接拉取整个目录
            return self._backup_directory(remote_source, local_target, organize_after_backup, dry_run)

        # Step 2: 逐个文件拉取
        if not dry_run:
            local_target.mkdir(parents=True, exist_ok=True)

        for file_info in scan_result.files:
            try:
                local_path = local_target / file_info.name

                if not dry_run:
                    self.bridge.pull_file(file_info.path, local_path)
                    self.stats["backed_up"] += 1

                result["pulled_files"].append({
                    "remote": file_info.path,
                    "local": str(local_path),
                    "size": file_info.size,
                })
                logger.info(f"备份: {file_info.name} ({file_info.size/1024:.1f}KB)")

            except AdbError as e:
                result["errors"].append(f"{file_info.path}: {e}")
                self.stats["errors"] += 1

        # Step 3: 可选整理
        if organize_after_backup and not dry_run and result["pulled_files"]:
            try:
                self._run_pc_organizer(local_target)
                result["organized"] = True
            except Exception as e:
                result["errors"].append(f"整理失败: {e}")

        return result

    def _backup_directory(self, remote_source: str, local_target: Path,
                          organize: bool, dry_run: bool) -> Dict:
        """直接拉取整个目录"""
        result = {
            "remote_source": remote_source,
            "local_target": str(local_target),
            "pulled_directory": True,
            "organized": False,
            "errors": [],
            "dry_run": dry_run,
        }

        if not dry_run:
            try:
                self.bridge.pull_directory(remote_source, local_target)
                self.stats["backed_up"] = 1

                if organize:
                    self._run_pc_organizer(local_target)
                    result["organized"] = True

            except AdbError as e:
                result["errors"].append(str(e))
                self.stats["errors"] += 1

        return result

    def _run_pc_organizer(self, target_dir: Path):
        """对本地目录运行 PC 端文件整理"""
        try:
            from organizer import FileOrganizer
            pc_organizer = FileOrganizer(
                download_folder=target_dir,
                mode=self.mode,
            )
            pc_organizer.organize(dry_run=False)
        except ImportError:
            logger.warning("无法加载 PC 端整理器，跳过整理步骤。")

    # ── 手机端清理 ────────────────────────────────────────────

    def cleanup(self,
                remote_path: str = "/sdcard/Download",
                dry_run: bool = True,
                remove_temp: bool = True,
                remove_empty_dirs: bool = True,
                temp_patterns: Optional[List[str]] = None) -> Dict:
        """
        清理手机目录

        Args:
            remote_path: 目标目录
            dry_run: 预览模式
            remove_temp: 是否清理临时文件
            remove_empty_dirs: 是否删除空目录
            temp_patterns: 自定义临时文件模式

        Returns:
            清理结果
        """
        result = {
            "temp_files_removed": [],
            "empty_dirs_removed": [],
            "errors": [],
            "dry_run": dry_run,
        }

        # 默认临时文件模式
        patterns = temp_patterns or [
            "*.tmp", "*.temp", "*.crdownload",
            "*.bak", "*.old", "~$*",
            ".thumbnails/*",
            "*cache*",
        ]

        # 清理临时文件
        if remove_temp:
            for pattern in patterns:
                try:
                    matches = self.bridge.find_files(
                        remote_path,
                        pattern=pattern,
                        file_type="f",
                        max_depth=3,
                    )
                    for m in matches:
                        if not dry_run:
                            self.bridge.delete_file(m.path)
                            self.stats["deleted"] += 1
                        result["temp_files_removed"].append(m.path)
                except AdbError as e:
                    result["errors"].append(f"搜索 {pattern}: {e}")

        # 清理空目录
        if remove_empty_dirs:
            try:
                empty_dirs = self._find_empty_dirs(remote_path)
                # 从最深层开始删除
                empty_dirs.sort(key=lambda p: len(p.split("/")), reverse=True)
                for d in empty_dirs:
                    if not dry_run:
                        self.bridge.delete_directory(d, recursive=False)
                        self.stats["deleted"] += 1
                    result["empty_dirs_removed"].append(d)
            except AdbError as e:
                result["errors"].append(f"清理空目录: {e}")

        return result

    def _find_empty_dirs(self, remote_path: str, max_depth: int = 5) -> List[str]:
        """查找手机上的空目录"""
        empty_dirs = []

        try:
            # 获取所有子目录
            subdirs = self.bridge.find_files(
                remote_path,
                file_type="d",
                max_depth=max_depth,
            )

            for d in subdirs:
                try:
                    entries = self.bridge.list_files(d.path)
                    # 过滤掉 . 和 ..
                    real_entries = [e for e in entries if e.name not in (".", "..")]
                    if not real_entries:
                        empty_dirs.append(d.path)
                except AdbError:
                    continue

        except AdbError:
            pass

        return empty_dirs

    # ── 手机端查重（仅文件名+大小级别）────────────────────────

    def find_duplicates(self,
                        remote_path: str,
                        max_depth: int = 3) -> List[Dict]:
        """
        在手机上查找可能的重复文件

        注意: ADB 拉取文件计算 MD5 速度很慢，
        此处使用 (文件名+大小) 作为重复判断依据。

        Args:
            remote_path: 目标目录
            max_depth: 搜索深度

        Returns:
            重复文件分组 [{name, size, files: [...]}, ...]
        """
        scan_result = self.scanner.scan_directory(
            remote_path,
            max_depth=max_depth,
            include_hidden=False,
        )

        # 按 (文件名, 大小) 分组
        groups: Dict[str, List[PhoneFileInfo]] = {}
        for f in scan_result.files:
            key = f"{f.name}:{f.size}"
            if key not in groups:
                groups[key] = []
            groups[key].append(f)

        # 只保留有重复的组
        duplicates = []
        for key, files in groups.items():
            if len(files) > 1:
                name, size = key.split(":", 1)
                duplicates.append({
                    "name": name,
                    "size": int(size),
                    "file_count": len(files),
                    "files": [{"path": f.path, "modified": str(f.modified_time)}
                              for f in files],
                })

        duplicates.sort(key=lambda d: d["size"], reverse=True)
        return duplicates

    # ── 全量诊断 ──────────────────────────────────────────────

    def diagnose(self, remote_path: str = "/sdcard",
                 max_depth: int = 3) -> Dict:
        """
        全面诊断手机文件状况

        Returns:
            诊断报告
        """
        report = {
            "device_info": {},
            "storage": {},
            "top_directories": [],
            "large_files": [],
            "redundant_files": [],
            "recommendations": [],
        }

        # 设备信息
        try:
            devices = self.bridge.detect_devices()
            if devices:
                d = devices[0]
                report["device_info"] = {
                    "model": d.model,
                    "manufacturer": d.manufacturer,
                    "android_version": d.android_version,
                    "battery_level": d.battery_level,
                }
        except Exception:
            pass

        # 存储信息
        try:
            report["storage"] = self.bridge.get_storage_info()
        except Exception:
            pass

        # 扫描主要目录
        summary_files = []

        for dir_name, dir_info in PHONE_DIRECTORIES.items():
            for path in dir_info["paths"]:
                try:
                    scan = self.scanner.scan_directory(
                        path, max_depth=dir_info.get("scan_depth", 1)
                    )
                    if scan.files:
                        summary_files.append({
                            "name": dir_name,
                            "path": path,
                            "files": scan.file_count,
                            "size": scan.total_size,
                            "size_formatted": scan.total_size_formatted,
                        })
                        break  # 一个分类只取第一个存在的路径
                except AdbError:
                    continue

        report["top_directories"] = sorted(
            summary_files, key=lambda x: x["size"], reverse=True
        )

        # 大文件
        large = self.scanner.find_large_files(remote_path, min_size_mb=100, max_depth=3)
        report["large_files"] = [
            {"path": f.path, "name": f.name, "size": f.size,
             "size_mb": round(f.size / (1024 * 1024), 1)}
            for f in large.files[:20]
        ]

        # 建议
        storage = report.get("storage", {})
        if storage.get("internal_free", 0) < 500 * 1024 * 1024:
            report["recommendations"].append(
                "⚠️ 手机可用空间不足 500MB，建议立即清理"
            )
        if large.files:
            report["recommendations"].append(
                f"📦 发现 {len(large.files)} 个大文件 (>100MB)，建议审查或备份到电脑"
            )

        return report

    # ── 设备信息 ──────────────────────────────────────────────

    def get_device_summary(self) -> Dict:
        """获取设备摘要信息"""
        try:
            devices = self.bridge.detect_devices(force_refresh=True)
            if not devices:
                return {"error": "未检测到设备"}

            d = devices[0]
            storage = self.bridge.get_storage_info()

            free_gb = storage.get("internal_free", 0) / (1024**3)
            total_gb = storage.get("internal_total", 0) / (1024**3)

            return {
                "device": d.model or d.id,
                "manufacturer": d.manufacturer,
                "android": d.android_version,
                "battery": f"{d.battery_level}%" if d.battery_level >= 0 else "未知",
                "storage": {
                    "total": f"{total_gb:.1f} GB",
                    "free": f"{free_gb:.1f} GB",
                    "usage": f"{(1 - free_gb/total_gb)*100:.0f}%" if total_gb > 0 else "未知",
                },
                "download_size": self._format_size(storage.get("download_size", 0)),
                "dcim_size": self._format_size(storage.get("dcim_size", 0)),
            }
        except (DeviceNotFoundError, AdbError) as e:
            return {"error": str(e)}

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
