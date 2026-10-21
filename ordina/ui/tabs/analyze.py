"""
Tab · 分析
==========
左侧 Canvas 柱状图（扩展名分布 Top 10），右侧统计表 + 关键指标卡片。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog

from ..theme import FONTS
from ..widgets import (
    SortableTreeview, attach_scrollbar, button, card, empty_state,
    format_size, label, stat_row,
)
from .base import BaseTab


class AnalyzeTab(BaseTab):
    title = "分析"
    icon = "📊"

    def build(self) -> None:
        top = card(self, self.theme, "分析操作")
        top.master.pack(fill=tk.X, padx=10, pady=(10, 6))

        actions = tk.Frame(top)
        self.theme.track(actions, bg="surface")
        actions.pack(fill=tk.X)
        button(actions, self.theme, "执行分析  F5", self.analyze, "accent").pack(side=tk.LEFT, padx=(0, 6))
        button(actions, self.theme, "导出 Markdown", self.export_markdown, "success").pack(side=tk.LEFT, padx=(0, 6))
        button(actions, self.theme, "导出 JSON", self.export_json, "default").pack(side=tk.LEFT, padx=(0, 6))
        button(actions, self.theme, "导出 CSV", self.export_csv, "default").pack(side=tk.LEFT)

        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # ── 图表 ──
        chart = card(pane, self.theme, "扩展名分布 Top 10")
        chart.master.configure(width=380)
        pane.add(chart.master, weight=1)

        self.canvas = tk.Canvas(chart, height=300, highlightthickness=0, bd=0)
        self.theme.track(self.canvas, bg="canvas_bg")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.theme.add_hook(self._redraw)
        self._chart_data = []

        # ── 统计 ──
        stats = card(pane, self.theme, "统计详情")
        pane.add(stats.master, weight=1)

        self.kpi_frame = tk.Frame(stats)
        self.theme.track(self.kpi_frame, bg="surface")
        self.kpi_frame.pack(fill=tk.X, pady=(0, 8))

        columns = (
            ("metric", "指标", 160, tk.W),
            ("value", "数值", 200, tk.W),
        )
        self.tree = SortableTreeview(stats, self.theme, columns,
                                     sortable=("metric", "value"))
        scrollbar = attach_scrollbar(self.tree, self.theme)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.empty = empty_state(stats, self.theme, "📊", "尚未分析",
                                 "选择文件夹后点击「执行分析」")
        self.empty.place(in_=stats, relx=0.5, rely=0.5, anchor=tk.CENTER)

    # ── 分析 ──────────────────────────────────────────────────

    def analyze(self) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return
        self.set_status("正在分析目录…")
        self.run_async(self._do_analyze)

    def _do_analyze(self) -> None:
        organizer = self.app.get_organizer()
        try:
            analysis = organizer.analyze()
        except Exception as exc:
            self.app.after_ui(lambda: self.error("分析失败", str(exc)))
            return
        self.app.after_ui(lambda: self._render(analysis))

    def _render(self, analysis: dict) -> None:
        self.tree.clear()
        self.empty.place_forget()
        for widget in self.kpi_frame.winfo_children():
            widget.destroy()

        total_mb = analysis.get("total_size_bytes", 0) / (1024 * 1024)
        stale_mb = analysis.get("stale_size_bytes", 0) / (1024 * 1024)

        # 关键指标
        stat_row(self.kpi_frame, self.theme, "总占用", f"{total_mb:.1f} MB", "accent").pack(fill=tk.X, pady=1)
        stat_row(self.kpi_frame, self.theme, "文件 / 目录",
                 f"{analysis.get('total_files', 0):,} / {analysis.get('total_dirs', 0):,}").pack(fill=tk.X, pady=1)
        stat_row(self.kpi_frame, self.theme, "重复组",
                 f"{len(analysis.get('duplicates', []))} 组", "warning").pack(fill=tk.X, pady=1)

        rows = [
            ("过期文件", f"{analysis.get('stale_count', 0)} 个（{stale_mb:.1f} MB）"),
            ("大文件 >100MB", f"{analysis.get('large_count', 0)} 个"),
            ("临时文件", f"{analysis.get('temp_count', 0)} 个"),
            ("空目录", f"{analysis.get('empty_dir_count', 0)} 个"),
        ]
        for metric, value in rows:
            self.tree.insert_row((metric, value))

        # 分类分布
        distribution = analysis.get("category_distribution", {})
        for category, info in sorted(distribution.items(),
                                     key=lambda kv: kv[1].get("size_bytes", 0), reverse=True):
            self.tree.insert_row((category, f"{info.get('count', 0)} 个 · "
                                            f"{format_size(info.get('size_bytes', 0))}"))

        by_ext = analysis.get("by_extension", {})
        top = sorted(by_ext.items(), key=lambda kv: kv[1][0], reverse=True)[:10]
        self._chart_data = [(ext or "(无扩展名)", count) for ext, (count, _) in top]
        self._redraw()

        self.set_status("分析完成")

    # ── 图表绘制 ──────────────────────────────────────────────

    def _redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 20 or height < 20:
            return

        colors = self.theme.colors.get("chart")
        if not isinstance(colors, list):
            colors = ["#4C8DFF"] * 10

        if not self._chart_data:
            canvas.create_text(width // 2, height // 2, text="暂无数据",
                               fill=self.theme.color("fg_subtle"), font=FONTS["body"])
            return

        max_value = max(value for _, value in self._chart_data) or 1
        label_width = 96
        value_width = 52
        bar_left = label_width
        bar_area = max(width - label_width - value_width - 16, 40)

        row_height = min(26, max(18, (height - 24) // max(len(self._chart_data), 1)))
        top = 12

        # 网格
        for i in range(5):
            x = bar_left + bar_area * i / 4
            canvas.create_line(x, 8, x, height - 8,
                               fill=self.theme.color("canvas_grid"), dash=(2, 4))

        for index, (name, value) in enumerate(self._chart_data):
            y = top + index * (row_height + 4)
            bar_width = max(int(bar_area * value / max_value), 3)
            color = colors[index % len(colors)]

            canvas.create_text(label_width - 8, y + row_height / 2, text=name[:12],
                               anchor=tk.E, fill=self.theme.color("fg_muted"),
                               font=FONTS["small"])
            canvas.create_rectangle(bar_left, y + 3, bar_left + bar_width, y + row_height - 3,
                                    fill=color, outline="")
            canvas.create_text(bar_left + bar_width + 6, y + row_height / 2,
                               text=str(value), anchor=tk.W,
                               fill=self.theme.color("fg"), font=FONTS["small"])

    # ── 导出 ──────────────────────────────────────────────────

    def _export(self, suffix: str, filetypes, writer) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=suffix, filetypes=filetypes,
                                            title="导出分析报告")
        if not path:
            return
        self.run_async(self._do_export, path, writer)

    def _do_export(self, path: str, writer) -> None:
        from pathlib import Path

        organizer = self.app.get_organizer()
        try:
            analysis = organizer.analyze()
            writer(analysis, Path(path))
        except Exception as exc:
            self.app.after_ui(lambda: self.error("导出失败", str(exc)))
            return
        self.app.after_ui(lambda: self.info("导出成功", f"报告已保存到：\n{path}"))
        self.app.after_ui(lambda: self.set_status(f"报告已导出：{path}"))

    def export_markdown(self) -> None:
        from ...core import Reporter
        self._export(".md", [("Markdown", "*.md"), ("所有文件", "*.*")],
                     lambda data, p: Reporter().to_markdown(data, p))

    def export_json(self) -> None:
        from ...core import Reporter
        self._export(".json", [("JSON", "*.json"), ("所有文件", "*.*")],
                     lambda data, p: Reporter().to_json(data, p))

    def export_csv(self) -> None:
        from ...core import Reporter

        def write_csv(data: dict, path: str) -> None:
            rows = []
            for category, info in data.get("category_distribution", {}).items():
                rows.append({"分类": category, "文件数": info.get("count", 0),
                             "占用": format_size(info.get("size_bytes", 0))})
            for ext, (count, size) in data.get("by_extension", {}).items():
                rows.append({"分类": ext or "(无扩展名)", "文件数": count,
                             "占用": format_size(size)})
            Reporter().to_csv(rows, path)

        self._export(".csv", [("CSV", "*.csv"), ("所有文件", "*.*")], write_csv)

    # ── 生命周期 ──────────────────────────────────────────────

    def on_folder_changed(self) -> None:
        self.tree.clear()
        self._chart_data = []
        self._redraw()
        self.empty.place(in_=self.tree.master, relx=0.5, rely=0.5, anchor=tk.CENTER)

    def refresh(self) -> None:
        if self.app.selected_folder.get():
            self.analyze()
