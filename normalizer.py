"""
命名规范化引擎
- 数字前缀：01_、02_ 前缀使文件夹固定排序
- 日期后缀：追加 _YYYYMMDD 实现版本追溯
- 批量重命名：按规则统一处理
- 冲突检测与自动解决
"""

import os
import re
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Callable

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config import DATE_SUFFIX_FORMAT

logger = logging.getLogger(__name__)


class NameNormalizer:
    """
    命名规范化器

    遵循知乎文章的文件管理哲学：
    1. 文件加日期后缀 `_YYYYMMDD`
    2. 文件夹加数字前缀 `01_`、`02_`
    3. 避免深层嵌套
    """

    def __init__(self, prefix_separator: str = "_", date_format: str = DATE_SUFFIX_FORMAT):
        """
        Args:
            prefix_separator: 数字前缀后的分隔符
            date_format: 日期后缀格式
        """
        self.prefix_separator = prefix_separator
        self.date_format = date_format

    # ── 日期提取 ──────────────────────────────────────────────

    def extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        从文件名中提取日期

        支持格式：
        - YYYYMMDD, YYYY-MM-DD, YYYY_MM_DD
        - YYMMDD
        - YYYY年MM月DD日
        """
        patterns = [
            (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),                      # 20220523
            (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),                  # 2022-05-23
            (r"(\d{4})_(\d{2})_(\d{2})", "%Y_%m_%d"),                  # 2022_05_23
            (r"(\d{4})年(\d{2})月(\d{2})日", "%Y年%m月%d日"),          # 2022年05月23日
            (r"(\d{2})(\d{2})(\d{2})", "%y%m%d"),                      # 220523（必须在最后，避免误匹配）
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    date_str = match.group(0)
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

        return None

    def extract_date_from_file(self, file_path: Path) -> Optional[datetime]:
        """
        提取文件的最佳日期
        优先级：文件名日期 > EXIF日期 > 修改时间 > 创建时间
        """
        # 1. 尝试从文件名提取
        fn_date = self.extract_date_from_filename(file_path.stem)
        if fn_date:
            return fn_date

        # 2. 尝试 EXIF
        try:
            from .recognizer import SmartRecognizer
            recognizer = SmartRecognizer()
            exif = recognizer.detect_exif(file_path)
            if exif.get("date_taken"):
                return exif["date_taken"]
        except Exception:
            pass

        # 3. 使用修改时间
        try:
            mtime = file_path.stat().st_mtime
            return datetime.fromtimestamp(mtime)
        except OSError:
            pass

        # 4. 使用创建时间
        try:
            ctime = file_path.stat().st_ctime
            return datetime.fromtimestamp(ctime)
        except OSError:
            pass

        return None

    # ── 日期后缀 ────────────────────────────────────────────────

    def add_date_suffix(self, file_path: Path, date: Optional[datetime] = None) -> str:
        """
        生成带日期后缀的新文件名

        Args:
            file_path: 原文件路径
            date: 指定的日期，None 则自动提取

        Returns:
            新文件名（不含路径）

        Example:
            "报告.pdf" → "报告_20220523.pdf"
            "报告_20220501.pdf" → "报告_20220501.pdf"（已有日期不重复添加）
        """
        stem = file_path.stem
        ext = file_path.suffix

        # 检查是否已有日期后缀
        existing_date = self.extract_date_from_filename(stem)
        if existing_date:
            return file_path.name

        # 提取或使用指定日期
        if date is None:
            date = self.extract_date_from_file(file_path)

        if date:
            date_str = date.strftime(self.date_format)
            return f"{stem}_{date_str}{ext}"

        # 无日期信息，使用当前日期
        date_str = datetime.now().strftime(self.date_format)
        return f"{stem}_{date_str}{ext}"

    def should_add_date_suffix(self, file_path: Path) -> bool:
        """判断是否需要添加日期后缀"""
        stem = file_path.stem
        existing_date = self.extract_date_from_filename(stem)
        return existing_date is None

    # ── 数字前缀（文件夹）──────────────────────────────────────

    def add_number_prefix(self, name: str, number: int, total: int = 8) -> str:
        """
        给文件夹名添加数字前缀

        Args:
            name: 原名称
            number: 编号 (1-99)
            total: 总数量（用于确定编号宽度）

        Returns:
            带前缀的名称

        Example:
            add_number_prefix("工作目录", 1, 8) → "01_工作目录"
        """
        width = len(str(total))
        prefix = f"{number:0{width}d}{self.prefix_separator}"
        return f"{prefix}{name}"

    def remove_number_prefix(self, name: str) -> str:
        """移除数字前缀"""
        match = re.match(r"^\d+[_\-\s.]?(.+)", name)
        if match:
            return match.group(1)
        return name

    def has_number_prefix(self, name: str) -> bool:
        """检查是否已有数字前缀"""
        return bool(re.match(r"^\d+[_\-\s.]", name))

    # ── 批量重命名 ──────────────────────────────────────────────

    def preview_rename(self, file_paths: List[Path],
                       add_date: bool = True,
                       date: Optional[datetime] = None) -> List[Tuple[Path, str]]:
        """
        预览重命名结果（不实际执行）

        Returns:
            [(原路径, 新文件名), ...]
        """
        preview = []
        for fp in file_paths:
            if not fp.is_file():
                continue
            if add_date and self.should_add_date_suffix(fp):
                new_name = self.add_date_suffix(fp, date)
                preview.append((fp, new_name))
        return preview

    def execute_rename(self, file_paths: List[Path],
                       add_date: bool = True,
                       date: Optional[datetime] = None,
                       dry_run: bool = True) -> List[Tuple[Path, Path]]:
        """
        执行重命名

        Returns:
            [(原路径, 新路径), ...]
        """
        results = []
        for fp in file_paths:
            if not fp.is_file() or not fp.exists():
                continue

            if add_date and self.should_add_date_suffix(fp):
                new_name = self.add_date_suffix(fp, date)
                new_path = fp.parent / new_name

                # 冲突处理
                new_path = self._resolve_conflict(new_path)

                if not dry_run:
                    try:
                        fp.rename(new_path)
                        logger.info(f"重命名: {fp.name} → {new_name}")
                        results.append((fp, new_path))
                    except OSError as e:
                        logger.error(f"重命名失败: {fp.name} - {e}")
                else:
                    results.append((fp, new_path))

        return results

    @staticmethod
    def _resolve_conflict(target_path: Path) -> Path:
        """解决文件名冲突：自动添加序号"""
        if not target_path.exists():
            return target_path

        stem = target_path.stem
        ext = target_path.suffix
        counter = 1
        while True:
            new_path = target_path.parent / f"{stem}_{counter:03d}{ext}"
            if not new_path.exists():
                return new_path
            counter += 1

    # ── 规范化检查 ──────────────────────────────────────────────

    def diagnose(self, directory: Path) -> Dict[str, List[Path]]:
        """
        诊断目录命名规范问题

        Returns:
            {
                "needs_date_suffix": [...],  # 缺少日期后缀的文件
                "needs_prefix": [...],       # 缺少数字前缀的文件夹
                "has_duplicate_names": [...],# 可能的命名冲突
                "too_deep_nested": [...],    # 嵌套过深的路径
                "irregular_names": [...],     # 命名不规范的项
            }
        """
        diagnosis = {
            "needs_date_suffix": [],
            "needs_prefix": [],
            "has_duplicate_names": [],
            "too_deep_nested": [],
            "irregular_names": [],
        }

        # 收集所有文件（递归）
        all_files = list(directory.rglob("*"))

        # 检查嵌套深度
        for item in all_files:
            if item.is_file():
                depth = len(item.relative_to(directory).parts)
                if depth > 3:  # 超过3层
                    diagnosis["too_deep_nested"].append(item)

                # 检查日期后缀
                if self.should_add_date_suffix(item):
                    diagnosis["needs_date_suffix"].append(item)

            elif item.is_dir():
                # 检查文件夹前缀
                if not self.has_number_prefix(item.name):
                    diagnosis["needs_prefix"].append(item)

        # 检测同名文件
        name_map: Dict[str, List[Path]] = {}
        for f in all_files:
            if f.is_file():
                name_map.setdefault(f.name, []).append(f)
        for name, paths in name_map.items():
            if len(paths) > 1:
                diagnosis["has_duplicate_names"].extend(paths)

        return diagnosis

    # ── 批量重命名文件夹（添加数字前缀）───────────────────────

    def add_prefixes_to_folders(self, directory: Path,
                                 prefix_map: Dict[str, int],
                                 dry_run: bool = True) -> List[Tuple[Path, Path]]:
        """
        给文件夹批量添加数字前缀

        Args:
            directory: 目标目录
            prefix_map: {文件夹名: 编号}
            dry_run: 预览模式

        Returns:
            [(原路径, 新路径), ...]
        """
        results = []
        for item in directory.iterdir():
            if not item.is_dir():
                continue
            if item.name in prefix_map and not self.has_number_prefix(item.name):
                number = prefix_map[item.name]
                new_name = self.add_number_prefix(item.name, number)
                new_path = item.parent / new_name

                if not dry_run:
                    try:
                        item.rename(new_path)
                        logger.info(f"文件夹前缀: {item.name} → {new_name}")
                        results.append((item, new_path))
                    except OSError as e:
                        logger.error(f"重命名失败: {item.name} - {e}")
                else:
                    results.append((item, new_path))

        return results
