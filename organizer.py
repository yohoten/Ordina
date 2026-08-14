"""
文件整理核心引擎 v2.0
集成分类器、识别器、规范化器和归档管理器
"""

import hashlib
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Union

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from classifiers import (
    BaseClassifier,
    ExtensionClassifier,
    PurposeClassifier,
    create_classifier,
)
from recognizer import SmartRecognizer
from normalizer import NameNormalizer
from archiver import ArchiveManager

logger = logging.getLogger(__name__)


class FileOrganizer:
    """
    文件整理核心引擎

    整合五大能力：
    1. 双模式文件分类（扩展名 + 用途）
    2. 智能文件识别
    3. 命名规范化（数字前缀 + 日期后缀）
    4. 重复文件检测
    5. 归档与清理
    """

    def __init__(self,
                 download_folder: Union[str, Path],
                 mode: str = "purpose",
                 custom_rules: Optional[Dict] = None,
                 classifier: Optional[BaseClassifier] = None):
        """
        Args:
            download_folder: 目标文件夹
            mode: 分类模式 "extension" | "purpose"
            custom_rules: 自定义分类规则
            classifier: 预构建的分类器实例
        """
        self.download_folder = Path(download_folder)
        self.mode = mode

        # 分类器
        if classifier is not None:
            self.classifier = classifier
        else:
            self.classifier = create_classifier(mode, custom_rules=custom_rules)

        # 辅助模块
        self.recognizer = SmartRecognizer()
        self.normalizer = NameNormalizer()
        self.archiver = ArchiveManager()

        # 日志
        self.log_dir = self.download_folder / ".organizer_logs"
        self.log_dir.mkdir(exist_ok=True)
        self._setup_logging()

        # 统计
        self.stats = self._init_stats()

    def _setup_logging(self):
        log_path = self.log_dir / f"organize_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        handler = logging.FileHandler(str(log_path), encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    @staticmethod
    def _init_stats() -> Dict:
        return {
            "processed": 0,
            "moved": 0,
            "renamed": 0,
            "archived": 0,
            "cleaned": 0,
            "skipped": 0,
            "duplicates": 0,
            "errors": 0,
        }

    # ── 分类 ────────────────────────────────────────────────────

    def get_file_category(self, file_path: Path) -> str:
        """获取文件分类（支持分类器上下文信息）"""
        kwargs = {}

        # 为 PurposeClassifier 提供识别上下文
        if self.mode == "purpose":
            exif = self.recognizer.detect_exif(file_path)
            kwargs["exif_info"] = exif

            source = self.recognizer.detect_download_source(file_path)
            kwargs["source_info"] = source or ""

        return self.classifier.classify(file_path, **kwargs)

    # ── 查重 ────────────────────────────────────────────────────

    def calculate_md5(self, file_path: Path, chunk_size: int = 8192) -> Optional[str]:
        """计算文件 MD5"""
        md5_hash = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            logger.error(f"MD5 计算失败: {file_path} - {e}")
            return None

    def find_duplicates(self) -> List[Dict]:
        """查找重复文件（基于文件大小+MD5）"""
        size_map = defaultdict(list)

        # 按大小分组
        for file_path in self.download_folder.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                try:
                    size = file_path.stat().st_size
                    size_map[size].append(file_path)
                except Exception as e:
                    logger.error(f"读取失败: {file_path} - {e}")

        duplicates = []
        for size, files in size_map.items():
            if len(files) < 2:
                continue

            hash_map = defaultdict(list)
            for fp in files:
                md5 = self.calculate_md5(fp)
                if md5:
                    hash_map[md5].append(fp)

            for md5, dup_files in hash_map.items():
                if len(dup_files) > 1:
                    duplicates.append({
                        "md5": md5,
                        "size": size,
                        "files": sorted(dup_files, key=lambda f: f.name),
                    })
                    self.stats["duplicates"] += len(dup_files) - 1

        # 保持稳定排序
        duplicates.sort(key=lambda d: d["size"], reverse=True)
        return duplicates

    # ── 整理 ────────────────────────────────────────────────────

    def organize(self,
                 dry_run: bool = True,
                 use_date_grouping: bool = False,
                 add_date_suffix: bool = False,
                 use_number_prefix: bool = True) -> Tuple[List, List]:
        """
        执行文件整理

        Args:
            dry_run: 预览模式（不实际操作）
            use_date_grouping: 按日期分组到子目录
            add_date_suffix: 文件添加日期后缀
            use_number_prefix: 分类文件夹使用数字前缀

        Returns:
            (moved_files, duplicates)
        """
        self.stats = self._init_stats()
        moved_files = []

        print(f"\n{'=' * 60}")
        print(f"[Organize] {self.download_folder}")
        print(f"   Mode: {'Purpose' if self.mode == 'purpose' else 'Extension'}")
        print(f"   Action: {'DRY-RUN' if dry_run else 'EXECUTE'}")
        print(f"{'=' * 60}\n")

        # 第一步：查重
        print("[Step 1] Checking for duplicate files...")
        duplicates = self.find_duplicates()
        if duplicates:
            dup_report = self._format_duplicates(duplicates, brief=True)
            print(dup_report)
        else:
            print("   [OK] No duplicates found.\n")

        # 第二步：收集并分类所有文件
        all_files = [f for f in self.download_folder.iterdir()
                     if f.is_file() and not f.name.startswith('.')]

        categories_found: Dict[str, List[Path]] = defaultdict(list)
        for fp in all_files:
            self.stats["processed"] += 1
            cat = self.get_file_category(fp)
            categories_found[cat].append(fp)

        # 第三步：按分类移动文件
        category_names = list(categories_found.keys())
        # 保证 "08_存档资料" 在最后
        if "08_存档资料" in category_names:
            category_names.remove("08_存档资料")
            category_names.append("08_存档资料")

        for cat in category_names:
            files = categories_found[cat]
            if not files:
                continue

            # 确定目标目录
            if use_number_prefix:
                # PURPOSE_CATEGORIES 的 key 已自带数字前缀（如 "01_工作目录"），直接使用
                if self._has_number_prefix(cat):
                    target_dir_name = cat
                else:
                    prefix = self._get_prefix_for_category(cat)
                    target_dir_name = prefix + self._strip_prefix(cat)
            else:
                target_dir_name = self._strip_prefix(cat)

            target_dir = self.download_folder / target_dir_name

            print(f"\n[Category] {target_dir_name} ({len(files)} files):")

            for fp in files:
                try:
                    # 处理目标子目录
                    if use_date_grouping:
                        mtime = datetime.fromtimestamp(fp.stat().st_mtime)
                        final_dir = target_dir / mtime.strftime("%Y-%m")
                    else:
                        final_dir = target_dir

                    # 日期后缀
                    final_name = fp.name
                    if add_date_suffix and self.normalizer.should_add_date_suffix(fp):
                        final_name = self.normalizer.add_date_suffix(fp)

                    # 冲突处理
                    target_path = final_dir / final_name
                    if target_path.exists() and target_path != fp:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        new_stem = f"{Path(final_name).stem}_{timestamp}{Path(final_name).suffix}"
                        target_path = final_dir / new_stem

                    if not dry_run:
                        final_dir.mkdir(parents=True, exist_ok=True)
                        self._move_file(fp, target_path)
                        logger.info(f"移动: {fp.name} → {target_path.relative_to(self.download_folder)}")

                    self.stats["moved"] += 1
                    moved_files.append((fp.name, str(target_path.relative_to(self.download_folder))))
                    print(f"   [OK] {fp.name}")

                except Exception as e:
                    self.stats["errors"] += 1
                    logger.error(f"处理失败: {fp.name} - {e}")
                    print(f"   [ERR] {fp.name}: {e}")

        # 打印统计
        self._print_stats(dry_run)
        return moved_files, duplicates

    # ── 清理 ────────────────────────────────────────────────────

    def cleanup(self, dry_run: bool = True) -> Dict:
        """
        一键清理：临时文件 + 空目录

        Returns:
            清理结果统计
        """
        print(f"\n[Cleanup] 清理模式: {self.download_folder}")
        print(f"   操作模式: {'预览' if dry_run else '执行'}\n")

        result = {
            "temp_files": self.archiver.clean_temp_files(self.download_folder, dry_run=dry_run),
            "empty_dirs": self.archiver.remove_empty_dirs(self.download_folder, dry_run=dry_run),
        }

        print(f"   临时文件: {len(result['temp_files'])} 个")
        print(f"   空目录:   {len(result['empty_dirs'])} 个")

        if dry_run:
            print("\n   [WARN]  预览模式，未实际删除。")
            if result["temp_files"]:
                print("\n   将清理的临时文件:")
                for f in result["temp_files"][:20]:
                    print(f"     - {f.name}")

        return result

    # ── 分析 ────────────────────────────────────────────────────

    def analyze(self) -> Dict:
        """全量分析目标目录"""
        analysis = self.archiver.analyze_storage(self.download_folder)

        # 补充分类分布
        category_dist = defaultdict(lambda: {"count": 0, "size_bytes": 0})
        for item in self.download_folder.iterdir():
            if item.is_file() and not item.name.startswith('.'):
                cat = self.get_file_category(item)
                try:
                    size = item.stat().st_size
                except OSError:
                    size = 0
                category_dist[cat]["count"] += 1
                category_dist[cat]["size_bytes"] += size

        analysis["category_distribution"] = dict(category_dist)
        analysis["duplicates"] = self.find_duplicates()

        return analysis

    # ── 诊断 ────────────────────────────────────────────────────

    def diagnose(self) -> Dict:
        """
        全面诊断：命名规范 + 存储问题 + 归档建议

        Returns:
            综合诊断报告
        """
        print(f"\n[Diagnose] 诊断: {self.download_folder}\n")

        report = {
            "naming_issues": self.normalizer.diagnose(self.download_folder),
            "storage_analysis": self.archiver.analyze_storage(self.download_folder),
            "archive_plan": self.archiver.suggest_archive_plan(self.download_folder),
            "duplicates": self.find_duplicates(),
        }

        self._print_diagnosis(report)
        return report

    # ── 辅助方法 ────────────────────────────────────────────────

    def _get_prefix_for_category(self, category: str) -> str:
        """获取分类对应的数字前缀"""
        if self.mode == "purpose" and hasattr(self.classifier, "get_prefix"):
            return self.classifier.get_prefix(category)
        # 扩展名模式默认前缀
        defaults = {
            "文档": "01_", "图片": "02_", "视频": "03_", "音频": "04_",
            "压缩包": "05_", "代码": "06_", "安装包": "07_", "字体": "08_", "其他": "09_",
        }
        return defaults.get(category, "10_")

    @staticmethod
    def _has_number_prefix(name: str) -> bool:
        """检查是否已有数字前缀"""
        import re
        return bool(re.match(r"^\d{2}[_\-\s.]", name))

    @staticmethod
    def _strip_prefix(name: str) -> str:
        """去除已有的数字前缀"""
        import re
        return re.sub(r"^\d{2}[_\-\s.]", "", name)

    @staticmethod
    def _move_file(src: Path, dst: Path):
        """安全移动文件"""
        import shutil
        shutil.move(str(src), str(dst))

    def _format_duplicates(self, duplicates: List[Dict], brief: bool = True) -> str:
        """格式化重复文件报告"""
        lines = [f"\n   [WARN]  发现 {len(duplicates)} 组重复文件:"]
        for i, d in enumerate(duplicates[:5 if brief else len(duplicates)], 1):
            wasted = d["size"] * (len(d["files"]) - 1)
            lines.append(f"   第{i}组: {self._format_size(d['size'])} x {len(d['files'])} 个"
                         f" | 可释放 {self._format_size(wasted)}")
            if not brief:
                for f in d["files"]:
                    lines.append(f"     - {f.name}")
        if brief and len(duplicates) > 5:
            lines.append(f"   ... 还有 {len(duplicates) - 5} 组")
        return "\n".join(lines)

    def _print_stats(self, dry_run: bool):
        mode = "预览" if dry_run else "执行"
        print(f"\n{'=' * 60}")
        print(f"[Stats] 整理完成 ({mode}模式)")
        print(f"{'=' * 60}")
        print(f"   处理文件: {self.stats['processed']}")
        print(f"   移动文件: {self.stats['moved']}")
        print(f"   跳过文件: {self.stats['skipped']}")
        print(f"   重复文件: {self.stats['duplicates']}")
        print(f"   错误文件: {self.stats['errors']}")
        print(f"{'=' * 60}\n")

    def _print_diagnosis(self, report: Dict):
        """打印诊断报告"""
        naming = report["naming_issues"]
        storage = report["storage_analysis"]
        archive = report["archive_plan"]
        dups = report["duplicates"]

        print(f"[Naming] 命名问题:")
        print(f"   缺日期后缀: {len(naming['needs_date_suffix'])} 个文件")
        print(f"   缺数字前缀: {len(naming['needs_prefix'])} 个文件夹")
        print(f"   嵌套过深:   {len(naming['too_deep_nested'])} 个文件")

        print(f"\n[Storage] 存储状态:")
        print(f"   总大小:     {storage['total_size_bytes'] / (1024*1024):.1f} MB")
        print(f"   过期文件:   {storage['stale_count']} 个")
        print(f"   大文件:     {storage['large_count']} 个 (>100MB)")
        print(f"   临时文件:   {storage['temp_count']} 个")
        print(f"   空目录:     {storage['empty_dir_count']} 个")
        print(f"   重复组:     {len(dups)} 组")

        print(f"\n[Suggestions] 归档建议:")
        print(f"   建议归档:   {len(archive['stale_files'])} 个过期文件")
        print(f"   建议清理:   {len(archive['temp_files'])} 个临时文件")
        estimate = archive['estimated_savings_mb']
        print(f"   预计释放:   {estimate:.1f} MB")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
