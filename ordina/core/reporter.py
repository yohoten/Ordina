"""
统计报告生成器
- 文件类型分布
- 存储占比分析
- 操作历史报告
- JSON / CSV / Markdown 导出
"""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Reporter:
    """统计报告生成器"""

    def __init__(self):
        self.reports_dir: Optional[Path] = None

    # ── JSON 导出 ──────────────────────────────────────────────

    def to_json(self, data: Dict, filepath: Optional[Path] = None) -> str:
        """
        导出为 JSON

        Args:
            data: 要导出的数据
            filepath: 输出路径，None 则返回字符串

        Returns:
            JSON 字符串
        """
        # 将 Path 对象转为字符串
        serializable = self._make_serializable(data)
        json_str = json.dumps(serializable, indent=2, ensure_ascii=False)

        if filepath:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(json_str, encoding='utf-8')
            logger.info(f"JSON 报告已保存: {filepath}")

        return json_str

    # ── CSV 导出 ────────────────────────────────────────────────

    def to_csv(self, data: List[Dict], filepath: Path, columns: Optional[List[str]] = None):
        """
        导出为 CSV

        Args:
            data: 字典列表
            filepath: 输出路径
            columns: 指定列及顺序
        """
        if not data:
            logger.warning("无数据，跳过 CSV 导出")
            return

        filepath.parent.mkdir(parents=True, exist_ok=True)

        if columns is None:
            columns = list(data[0].keys())

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            # 转换 Path 对象
            for row in data:
                writer.writerow(self._make_serializable(row))

        logger.info(f"CSV 报告已保存: {filepath}")

    # ── Markdown 报告 ──────────────────────────────────────────

    def to_markdown(self, analysis: Dict, filepath: Optional[Path] = None) -> str:
        """
        生成 Markdown 格式的可读报告

        Args:
            analysis: 分析数据（来自 ArchiveManager.analyze_storage）
            filepath: 输出路径

        Returns:
            Markdown 文本
        """
        lines = []
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines.append(f"# [Stats] 文件整理报告")
        lines.append(f"")
        lines.append(f"**生成时间**: {ts}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        # 概览
        total_mb = analysis.get("total_size_bytes", 0) / (1024 * 1024)
        lines.append(f"## [Chart] 概览")
        lines.append(f"")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 文件总数 | {analysis.get('total_files', 0):,} |")
        lines.append(f"| 文件夹总数 | {analysis.get('total_dirs', 0):,} |")
        lines.append(f"| 总占用空间 | {total_mb:.1f} MB |")
        lines.append(f"")

        # 分类分布
        cat_dist = analysis.get("category_distribution", {})
        if cat_dist:
            lines.append(f"## 📂 分类分布")
            lines.append(f"")
            lines.append(f"| 分类 | 文件数 | 大小 |")
            lines.append(f"|------|--------|------|")
            for cat, info in sorted(cat_dist.items()):
                size_mb = info["size_bytes"] / (1024 * 1024)
                lines.append(f"| {cat} | {info['count']} | {size_mb:.1f} MB |")
            lines.append(f"")

        # 扩展名分布
        by_ext = analysis.get("by_extension", {})
        if by_ext:
            sorted_exts = sorted(by_ext.items(), key=lambda x: x[1][1], reverse=True)[:15]
            lines.append(f"## 🏷️ 扩展名 Top 15")
            lines.append(f"")
            lines.append(f"| 扩展名 | 数量 | 大小 |")
            lines.append(f"|--------|------|------|")
            for ext, (count, size) in sorted_exts:
                lines.append(f"| {ext or '(无)'} | {count} | {size / (1024*1024):.1f} MB |")
            lines.append(f"")

        # 问题
        lines.append(f"## [WARN] 需要关注")
        lines.append(f"")
        stale_count = analysis.get("stale_count", 0)
        stale_mb = analysis.get("stale_size_bytes", 0) / (1024 * 1024)
        large_count = analysis.get("large_count", 0)
        temp_count = analysis.get("temp_count", 0)
        empty_count = analysis.get("empty_dir_count", 0)

        lines.append(f"| 问题 | 数量 | 说明 |")
        lines.append(f"|------|------|------|")
        lines.append(f"| 过期文件 | {stale_count} | {stale_mb:.0f} MB，>90天未访问 |")
        lines.append(f"| 大文件 | {large_count} | >100 MB |")
        lines.append(f"| 临时文件 | {temp_count} | 建议清理 |")
        lines.append(f"| 空目录 | {empty_count} | 建议删除 |")
        lines.append(f"")

        # 重复文件
        duplicates = analysis.get("duplicates", [])
        if duplicates:
            total_dup_size = sum(d["size"] * (len(d["files"]) - 1) for d in duplicates)
            lines.append(f"## 🔁 重复文件")
            lines.append(f"")
            lines.append(f"共 {len(duplicates)} 组重复，可释放 {total_dup_size / (1024*1024):.1f} MB")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"*由 Ordina / 归序 自动生成*")

        md_text = "\n".join(lines)

        if filepath:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(md_text, encoding='utf-8')
            logger.info(f"Markdown 报告已保存: {filepath}")

        return md_text

    # ── 操作摘要 ────────────────────────────────────────────────

    def operation_summary(self, stats: Dict, moved_files: List,
                          duplicates: List, duration_seconds: float) -> str:
        """
        生成单次操作摘要

        Returns:
            人类可读的摘要文本
        """
        lines = [
            "=" * 60,
            "   [Naming] 操作摘要",
            "=" * 60,
            f"   耗时: {duration_seconds:.1f} 秒",
            f"   处理文件: {stats.get('processed', 0)}",
            f"   移动文件: {stats.get('moved', 0)}",
            f"   重命名:   {stats.get('renamed', 0)}",
            f"   归档:     {stats.get('archived', 0)}",
            f"   清理:     {stats.get('cleaned', 0)}",
            f"   重复文件: {stats.get('duplicates', 0)}",
            f"   错误:     {stats.get('errors', 0)}",
        ]
        if moved_files:
            lines.append(f"\n   移动详情 (前 10 条):")
            for old, new in moved_files[:10]:
                lines.append(f"   {old} → {new}")
            if len(moved_files) > 10:
                lines.append(f"   ... 还有 {len(moved_files) - 10} 个")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ── 辅助 ────────────────────────────────────────────────────

    @staticmethod
    def _make_serializable(obj):
        """递归转换 Path 等不可序列化对象"""
        from pathlib import Path as PathType
        if isinstance(obj, dict):
            return {k: Reporter._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [Reporter._make_serializable(item) for item in obj]
        elif isinstance(obj, PathType):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj
