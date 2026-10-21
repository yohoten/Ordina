"""
归档与清理管理器
- 时效检测：标记 N 天未访问的文件
- 大文件扫描：找出占用空间大的文件
- 空目录清理：递归检测空文件夹
- 临时文件清理：删除 .tmp / ~$ 等
- 智能归档建议
"""

import re
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from .config import (
    ARCHIVE_DAYS_THRESHOLD,
    LARGE_FILE_SIZE_MB,
    TEMP_FILE_EXTENSIONS,
    TEMP_FILE_PATTERNS,
)

logger = logging.getLogger(__name__)


class ArchiveManager:
    """归档与清理管理器"""

    def __init__(self, archive_days: int = ARCHIVE_DAYS_THRESHOLD,
                 large_size_mb: int = LARGE_FILE_SIZE_MB):
        self.archive_days = archive_days
        self.large_size_mb = large_size_mb
        self._compiled_temp_patterns = [re.compile(p) for p in TEMP_FILE_PATTERNS]

    # ── 时效检测 ──────────────────────────────────────────────

    def find_stale_files(self, directory: Path,
                          days: Optional[int] = None,
                          include_dirs: bool = False) -> List[Dict]:
        """
        查找超过 N 天未访问的文件

        Returns:
            [{"path": Path, "last_access": datetime, "age_days": int, "size": int}, ...]
        """
        threshold_days = days or self.archive_days
        cutoff = datetime.now() - timedelta(days=threshold_days)
        stale_files = []

        for item in directory.rglob("*"):
            try:
                stat = item.stat()
            except OSError:
                continue

            if item.is_file() or (include_dirs and item.is_dir()):
                last_access = datetime.fromtimestamp(stat.st_atime)
                if last_access < cutoff:
                    stale_files.append({
                        "path": item,
                        "last_access": last_access,
                        "age_days": (datetime.now() - last_access).days,
                        "size": stat.st_size if item.is_file() else 0,
                        "is_dir": item.is_dir(),
                    })

        # 按最后访问时间排序（最久远的排前面）
        stale_files.sort(key=lambda x: x["last_access"])
        return stale_files

    # ── 大文件扫描 ──────────────────────────────────────────────

    def find_large_files(self, directory: Path,
                          min_size_mb: Optional[int] = None) -> List[Dict]:
        """
        查找大文件

        Returns:
            [{"path": Path, "size_mb": float, "size_bytes": int, "extension": str}, ...]
        """
        threshold = (min_size_mb or self.large_size_mb) * 1024 * 1024
        large_files = []

        for item in directory.rglob("*"):
            if not item.is_file():
                continue
            try:
                size = item.stat().st_size
            except OSError:
                continue

            if size >= threshold:
                large_files.append({
                    "path": item,
                    "size_mb": size / (1024 * 1024),
                    "size_bytes": size,
                    "extension": item.suffix.lower(),
                })

        # 按文件大小降序
        large_files.sort(key=lambda x: x["size_bytes"], reverse=True)
        return large_files

    # ── 空目录清理 ──────────────────────────────────────────────

    def find_empty_dirs(self, directory: Path) -> List[Path]:
        """
        递归查找空目录

        Returns:
            空目录路径列表（按深度降序，子目录先于父目录）
        """
        empty_dirs = []

        for item in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if item.is_dir():
                try:
                    if not any(item.iterdir()):
                        empty_dirs.append(item)
                except OSError:
                    continue

        return empty_dirs

    def remove_empty_dirs(self, directory: Path, dry_run: bool = True) -> List[Path]:
        """
        删除空目录

        Returns:
            已删除的目录列表
        """
        removed = []
        empty_dirs = self.find_empty_dirs(directory)

        for dir_path in empty_dirs:
            if not dry_run:
                try:
                    dir_path.rmdir()
                    logger.info(f"删除空目录: {dir_path}")
                    removed.append(dir_path)
                except OSError as e:
                    logger.error(f"删除空目录失败: {dir_path} - {e}")
            else:
                removed.append(dir_path)

        return removed

    # ── 临时文件清理 ──────────────────────────────────────────

    def find_temp_files(self, directory: Path) -> List[Path]:
        """查找临时文件"""
        temp_files = []

        for item in directory.rglob("*"):
            if not item.is_file():
                continue

            name = item.name
            ext = item.suffix.lower()

            # 扩展名匹配
            if ext in TEMP_FILE_EXTENSIONS:
                temp_files.append(item)
                continue

            # 正则模式匹配
            for pattern in self._compiled_temp_patterns:
                if pattern.search(name):
                    temp_files.append(item)
                    break

        return temp_files

    def clean_temp_files(self, directory: Path, dry_run: bool = True) -> List[Path]:
        """
        清理临时文件

        Returns:
            已清理的文件列表
        """
        cleaned = []
        temp_files = self.find_temp_files(directory)

        for fp in temp_files:
            if not dry_run:
                try:
                    fp.unlink()
                    logger.info(f"清理临时文件: {fp.name}")
                    cleaned.append(fp)
                except OSError as e:
                    logger.error(f"清理临时文件失败: {fp.name} - {e}")
            else:
                cleaned.append(fp)

        return cleaned

    # ── 存储分析 ──────────────────────────────────────────────

    def analyze_storage(self, directory: Path) -> Dict:
        """
        存储空间分析

        Returns:
            {
                "total_size_bytes": int,
                "total_files": int,
                "total_dirs": int,
                "by_extension": {ext: (count, size_bytes)},
                "stale_count": int,
                "stale_size_bytes": int,
                "large_count": int,
                "temp_count": int,
                "empty_dir_count": int,
            }
        """
        analysis = {
            "total_size_bytes": 0,
            "total_files": 0,
            "total_dirs": 0,
            "by_extension": {},
            "stale_count": 0,
            "stale_size_bytes": 0,
            "large_count": 0,
            "temp_count": 0,
            "empty_dir_count": 0,
        }

        cutoff = datetime.now() - timedelta(days=self.archive_days)
        large_threshold = self.large_size_mb * 1024 * 1024

        for item in directory.rglob("*"):
            try:
                stat = item.stat()
            except OSError:
                continue

            if item.is_file():
                analysis["total_files"] += 1
                size = stat.st_size
                analysis["total_size_bytes"] += size

                # 按扩展名统计
                ext = item.suffix.lower()
                if ext not in analysis["by_extension"]:
                    analysis["by_extension"][ext] = [0, 0]
                analysis["by_extension"][ext][0] += 1
                analysis["by_extension"][ext][1] += size

                # 时效检查
                last_access = datetime.fromtimestamp(stat.st_atime)
                if last_access < cutoff:
                    analysis["stale_count"] += 1
                    analysis["stale_size_bytes"] += size

                # 大文件检查
                if size >= large_threshold:
                    analysis["large_count"] += 1

                # 临时文件检查
                if self._is_temp(item):
                    analysis["temp_count"] += 1

            elif item.is_dir():
                analysis["total_dirs"] += 1

        # 空目录计数
        analysis["empty_dir_count"] = len(self.find_empty_dirs(directory))

        return analysis

    def _is_temp(self, file_path: Path) -> bool:
        """检查是否为临时文件"""
        name = file_path.name
        ext = file_path.suffix.lower()
        if ext in TEMP_FILE_EXTENSIONS:
            return True
        for pattern in self._compiled_temp_patterns:
            if pattern.search(name):
                return True
        return False

    # ── 智能归档建议 ──────────────────────────────────────────

    def suggest_archive_plan(self, directory: Path) -> Dict:
        """
        生成智能归档建议

        Returns:
            {
                "stale_files": [...],      # 建议归档的文件
                "large_files": [...],      # 需要关注的大文件
                "temp_files": [...],       # 建议清理的临时文件
                "empty_dirs": [...],       # 可删除的空目录
                "estimated_savings_mb": float,  # 预计可释放空间
            }
        """
        plan = {
            "stale_files": self.find_stale_files(directory),
            "large_files": self.find_large_files(directory),
            "temp_files": self.find_temp_files(directory),
            "empty_dirs": self.find_empty_dirs(directory),
            "estimated_savings_mb": 0.0,
        }

        # 计算预计可释放空间
        for f in plan["temp_files"]:
            try:
                plan["estimated_savings_mb"] += f.stat().st_size / (1024 * 1024)
            except OSError:
                pass

        for d in plan["empty_dirs"]:
            # 空目录本身不占多少空间，跳过
            pass

        return plan

    # ── 批量归档操作 ──────────────────────────────────────────

    def archive_files(self, source_dir: Path, target_dir: Path,
                       files: List[Path], dry_run: bool = True) -> List[Tuple[Path, Path]]:
        """
        将文件归档到目标目录

        Args:
            source_dir: 源目录
            target_dir: 归档目标目录
            files: 要归档的文件列表
            dry_run: 预览模式

        Returns:
            [(源路径, 目标路径), ...]
        """
        results = []

        for fp in files:
            # 保持相对路径结构
            try:
                rel_path = fp.relative_to(source_dir)
            except ValueError:
                rel_path = fp.name

            target_path = target_dir / rel_path

            if not dry_run:
                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(fp), str(target_path))
                    logger.info(f"归档: {fp.name} → {target_path}")
                    results.append((fp, target_path))
                except OSError as e:
                    logger.error(f"归档失败: {fp.name} - {e}")
            else:
                results.append((fp, target_path))

        return results

    @staticmethod
    def format_report(analysis: Dict) -> str:
        """格式化存储分析报告为可读文本"""
        total_mb = analysis["total_size_bytes"] / (1024 * 1024)
        stale_mb = analysis["stale_size_bytes"] / (1024 * 1024)

        lines = [
            "=" * 60,
            "[Stats] 存储空间分析报告",
            "=" * 60,
            "",
            f"文件总数:     {analysis['total_files']:,}",
            f"文件夹总数:   {analysis['total_dirs']:,}",
            f"总占用空间:   {total_mb:.1f} MB",
            "",
            f"过期文件数:   {analysis['stale_count']}  "
            f"(占用 {stale_mb:.1f} MB, >{ARCHIVE_DAYS_THRESHOLD}天未访问)",
            f"大文件数:     {analysis['large_count']}  "
            f"(>{LARGE_FILE_SIZE_MB} MB)",
            f"临时文件数:   {analysis['temp_count']}",
            f"空目录数:     {analysis['empty_dir_count']}",
            "",
            "扩展名分布 (Top 10):",
        ]

        # 扩展名统计 Top 10
        by_ext = analysis["by_extension"]
        sorted_exts = sorted(by_ext.items(), key=lambda x: x[1][1], reverse=True)[:10]
        for ext, (count, size) in sorted_exts:
            lines.append(f"  {ext or '(无扩展名)':12s}  {count:5d} 个  "
                         f"{(size / (1024*1024)):8.1f} MB")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
