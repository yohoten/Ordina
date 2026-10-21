"""
Tab · 整理
==========
左侧：整理选项 + 命名规则（模板 / 日期来源 / 日期格式）+ 操作按钮
右侧：可勾选、可排序的整理预览表（勾选状态会真正影响执行范围）
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from ..theme import FONTS, ThemeManager
from ..widgets import (
    SortableTreeview, attach_scrollbar, button, card, empty_state,
    format_size, label, status_label,
)
from .base import BaseTab

from ...core import DateSource, TEMPLATE_PRESETS, NamingRules

DATE_FORMATS = ("%Y%m%d", "%Y-%m-%d", "%Y%m", "%Y%m%d_%H%M")


class OrganizeTab(BaseTab):
    title = "整理"
    icon = "📂"

    def build(self) -> None:
        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── 左栏 ──
        left = tk.Frame(pane, width=320)
        self.theme.track(left, bg="bg")
        left.pack_propagate(False)
        pane.add(left, weight=0)

        self._build_options(left)
        self._build_naming(left)
        self._build_actions(left)

        # ── 右栏 ──
        right = tk.Frame(pane)
        self.theme.track(right, bg="bg")
        pane.add(right, weight=1)
        self._build_preview(right)

    # ── 整理选项 ──────────────────────────────────────────────

    def _build_options(self, parent: tk.Misc) -> None:
        body = card(parent, self.theme, "整理选项")
        body.master.pack(fill=tk.X, pady=(0, 10))

        self.dry_run_var = tk.BooleanVar(value=True)
        self.date_group_var = tk.BooleanVar(value=False)
        self.date_suffix_var = tk.BooleanVar(value=True)
        self.num_prefix_var = tk.BooleanVar(value=True)

        checks = [
            ("预览模式（只看效果，不移动文件）", self.dry_run_var, True),
            ("按月份分组到子目录", self.date_group_var, False),
            ("按命名规则改写文件名", self.date_suffix_var, False),
            ("分类目录加数字前缀（01_ / 02_）", self.num_prefix_var, False),
        ]
        for text, var, emphasize in checks:
            cb = tk.Checkbutton(body, text=text, variable=var, font=FONTS["body"],
                                anchor=tk.W, cursor="hand2", borderwidth=0,
                                highlightthickness=0, padx=4, pady=3)
            self.theme.track(cb, bg="surface", fg="fg" if emphasize else "fg_muted",
                             selectcolor="entry_bg", activebackground="surface",
                             activeforeground="fg")
            cb.pack(fill=tk.X, pady=1)

    # ── 命名规则 ──────────────────────────────────────────────

    def _build_naming(self, parent: tk.Misc) -> None:
        body = card(parent, self.theme, "命名规则")
        body.master.pack(fill=tk.X, pady=(0, 10))

        rules = self.app.naming_rules
        self.template_var = tk.StringVar(value=rules.file_template)
        self.date_source_var = tk.StringVar(value=rules.date_source)
        self.date_format_var = tk.StringVar(value=rules.date_format)

        # 模板
        label(body, self.theme, "命名模板", "small", "fg_muted").pack(anchor=tk.W)
        template_names = [f"{t}    {d}" for t, d in TEMPLATE_PRESETS.items()]
        self.template_cb = ttk.Combobox(body, values=template_names, font=FONTS["body"],
                                        state="readonly")
        current_tpl = self.template_var.get()
        for index, (tpl, _) in enumerate(TEMPLATE_PRESETS.items()):
            if tpl == current_tpl:
                self.template_cb.current(index)
                break
        else:
            self.template_cb.set(current_tpl)
        self.template_cb.pack(fill=tk.X, pady=(2, 8))
        self.template_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_rules_changed())

        row = tk.Frame(body)
        self.theme.track(row, bg="surface")
        row.pack(fill=tk.X)

        left_col = tk.Frame(row)
        self.theme.track(left_col, bg="surface")
        left_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        label(left_col, self.theme, "日期来源", "small", "fg_muted").pack(anchor=tk.W)
        self.source_cb = ttk.Combobox(left_col, values=list(DateSource.CHOICES),
                                      state="readonly", font=FONTS["body"])
        self.source_cb.set(self.date_source_var.get())
        self.source_cb.pack(fill=tk.X, pady=(2, 0))
        self.source_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_rules_changed())

        right_col = tk.Frame(row)
        self.theme.track(right_col, bg="surface")
        right_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        label(right_col, self.theme, "日期格式", "small", "fg_muted").pack(anchor=tk.W)
        self.format_cb = ttk.Combobox(right_col, values=DATE_FORMATS,
                                      state="readonly", font=FONTS["body"])
        self.format_cb.set(self.date_format_var.get())
        self.format_cb.pack(fill=tk.X, pady=(2, 0))
        self.format_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_rules_changed())

        # 实时示例
        self.sample_var = tk.StringVar(value="")
        status_label(body, self.theme, self.sample_var, "accent").pack(anchor=tk.W, pady=(8, 0))
        self._update_sample()

    def _current_template(self) -> str:
        raw = self.template_cb.get().strip()
        return raw.split()[0] if raw else "{name}_{date}"

    def _on_rules_changed(self) -> None:
        self.app.naming_rules = NamingRules(
            file_template=self._current_template(),
            date_source=self.source_cb.get() or DateSource.AUTO,
            date_format=self.format_cb.get() or "%Y%m%d",
        )
        self.app.rebuild_organizer()
        self._update_sample()
        self.set_status(f"命名规则已更新：{self.app.naming_rules.summary()}")

    def _update_sample(self) -> None:
        normalizer = self.app.get_normalizer()
        try:
            sample = normalizer.build_name(
                "季度报告", ".pdf", date=datetime(2026, 3, 7), category="01_工作目录",
            )
            self.sample_var.set(f"示例：季度报告.pdf → {sample}")
        except Exception as exc:  # pragma: no cover
            self.sample_var.set(f"示例生成失败：{exc}")

    # ── 操作 ──────────────────────────────────────────────────

    def _build_actions(self, parent: tk.Misc) -> None:
        body = card(parent, self.theme, "操作")
        body.master.pack(fill=tk.X)

        button(body, self.theme, "预览整理  Ctrl+P",
               self.preview, "accent").pack(fill=tk.X, pady=2)
        button(body, self.theme, "执行整理  Ctrl+Enter",
               self.execute, "success").pack(fill=tk.X, pady=2)

        sep = tk.Frame(body, height=1)
        self.theme.track(sep, bg="border")
        sep.pack(fill=tk.X, pady=8)

        button(body, self.theme, "一键清理临时文件",
               self.cleanup, "warning").pack(fill=tk.X, pady=2)
        button(body, self.theme, "全面诊断",
               self.diagnose, "default").pack(fill=tk.X, pady=2)

    # ── 预览表 ────────────────────────────────────────────────

    def _build_preview(self, parent: tk.Misc) -> None:
        body = card(parent, self.theme, "整理预览")
        body.master.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(body)
        self.theme.track(toolbar, bg="surface")
        toolbar.pack(fill=tk.X, pady=(0, 8))

        for text, command in (
            ("全选", self._select_all),
            ("全不选", self._deselect_all),
            ("反选", self._invert),
        ):
            ttk.Button(toolbar, text=text, command=command,
                       style="Ghost.TButton").pack(side=tk.LEFT, padx=(0, 4))

        self.summary_var = tk.StringVar(value="选择文件夹后点击「预览整理」")
        status_label(toolbar, self.theme, self.summary_var).pack(side=tk.RIGHT)

        columns = (
            ("sel", "✓", 40, tk.CENTER),
            ("filename", "文件名", 220, tk.W),
            ("category", "分类", 110, tk.W),
            ("target", "目标路径", 260, tk.W),
            ("size", "大小", 90, tk.E),
            ("date", "修改日期", 120, tk.CENTER),
        )
        self.tree = SortableTreeview(
            body, self.theme, columns,
            sortable=("filename", "category", "target", "size", "date"),
            selectmode="extended",
        )
        self.tree.column("sel", stretch=False)
        self.tree.tag_configure("renamed", foreground=self.theme.color("accent"))
        self.theme.add_hook(self._repaint_tags)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        scrollbar = attach_scrollbar(self.tree, self.theme)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.empty = empty_state(body, self.theme, "📂",
                                 "尚未预览",
                                 "Ctrl+O 选择文件夹，然后 Ctrl+P 预览整理效果")
        self.empty.place(in_=body, relx=0.5, rely=0.5, anchor=tk.CENTER)

    def _repaint_tags(self) -> None:
        self.tree.tag_configure("renamed", foreground=self.theme.color("accent"))

    # ── 勾选 ──────────────────────────────────────────────────

    def _on_tree_click(self, event: tk.Event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        item = self.tree.identify_row(event.y)
        if item:
            current = self.tree.set(item, "sel")
            self.tree.set(item, "sel", "" if current == "✓" else "✓")

    def _select_all(self) -> None:
        for item in self.tree.get_children():
            self.tree.set(item, "sel", "✓")

    def _deselect_all(self) -> None:
        for item in self.tree.get_children():
            self.tree.set(item, "sel", "")

    def _invert(self) -> None:
        for item in self.tree.get_children():
            current = self.tree.set(item, "sel")
            self.tree.set(item, "sel", "" if current == "✓" else "✓")

    def _selected_names(self) -> set:
        names = set()
        for item in self.tree.get_children():
            if self.tree.set(item, "sel") == "✓":
                names.add(self.tree.set(item, "filename"))
        return names

    # ── 动作 ──────────────────────────────────────────────────

    def preview(self) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return

        self.tree.clear()
        self.empty.place_forget()
        self.summary_var.set("正在分析…")
        self.set_status("正在预览整理效果…")

        try:
            moved, duplicates = organizer.organize(
                dry_run=True,
                use_date_grouping=self.date_group_var.get(),
                add_date_suffix=self.date_suffix_var.get(),
                use_number_prefix=self.num_prefix_var.get(),
                verbose=False,
            )
        except Exception as exc:
            self.error("预览失败", str(exc))
            return

        folder = Path(self.app.selected_folder.get())
        for old_name, target_rel in moved:
            source = folder / old_name
            try:
                stat = source.stat()
                size = format_size(stat.st_size)
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                size, mtime = "—", "—"

            target_name = Path(target_rel).name
            tags = ("renamed",) if target_name != old_name else ()
            self.tree.insert_row(
                ("✓", old_name, Path(target_rel).parent.name, target_rel, size, mtime),
                tags,
            )

        count = len(moved)
        self.summary_var.set(
            f"{count} 个文件待整理"
            + (f" · {len(duplicates)} 组重复" if duplicates else "")
        )
        self.set_status(f"预览完成 — {count} 个文件将按 {organizer.mode} 模式归类")

    def execute(self) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return

        if self.dry_run_var.get():
            if not self.ask_yes("确认", "当前为预览模式，是否切换为实际执行？"):
                return
            self.dry_run_var.set(False)

        selected = self._selected_names()
        if self.tree.get_children() and not selected:
            self.warn("提示", "未勾选任何文件。请先在预览表中勾选要整理的文件。")
            return

        if not self.ask_yes("确认执行", "整理后文件将被移动到分类目录，此操作不可撤销。\n\n是否继续？"):
            return

        self.run_async(self._do_execute, selected or None)

    def _do_execute(self, only_names) -> None:
        organizer = self.app.get_organizer()
        try:
            moved, _ = organizer.organize(
                dry_run=False,
                use_date_grouping=self.date_group_var.get(),
                add_date_suffix=self.date_suffix_var.get(),
                use_number_prefix=self.num_prefix_var.get(),
                verbose=False,
                only_names=only_names,
            )
        except Exception as exc:
            self.app.after_ui(lambda: self.error("整理失败", str(exc)))
            return
        self.app.after_ui(lambda: self.info("完成", f"已整理 {len(moved)} 个文件。"))
        self.app.after_ui(lambda: self.set_status(f"整理完成 — 移动 {len(moved)} 个文件"))
        self.app.after_ui(self.preview)

    def cleanup(self) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return
        if not self.ask_yes("确认清理", "将清理临时文件（.tmp / ~$ / .crdownload 等）与空目录。\n\n是否继续？"):
            return
        self.run_async(self._do_cleanup)

    def _do_cleanup(self) -> None:
        organizer = self.app.get_organizer()
        dry_run = self.dry_run_var.get()
        try:
            result = organizer.cleanup(dry_run=dry_run)
        except Exception as exc:
            self.app.after_ui(lambda: self.error("清理失败", str(exc)))
            return
        message = (f"临时文件 {len(result['temp_files'])} 个、"
                   f"空目录 {len(result['empty_dirs'])} 个"
                   f"（{'预览' if dry_run else '已清理'}）")
        self.app.after_ui(lambda: self.info("清理完成", message))
        self.app.after_ui(lambda: self.set_status(f"清理完成 — {message}"))

    def diagnose(self) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return
        self.run_async(self._do_diagnose)

    def _do_diagnose(self) -> None:
        organizer = self.app.get_organizer()
        try:
            report = organizer.diagnose()
        except Exception as exc:
            self.app.after_ui(lambda: self.error("诊断失败", str(exc)))
            return

        naming = report.get("naming_issues", {})
        storage = report.get("storage_analysis", {})
        archive = report.get("archive_plan", {})
        total_mb = storage.get("total_size_bytes", 0) / (1024 * 1024)

        summary = (
            f"命名：缺日期 {len(naming.get('needs_date_suffix', []))} 个、"
            f"缺前缀 {len(naming.get('needs_prefix', []))} 个、"
            f"不合规 {len(naming.get('irregular_names', []))} 个、"
            f"嵌套过深 {len(naming.get('too_deep_nested', []))} 个\n\n"
            f"存储：共 {total_mb:.1f} MB、"
            f"过期 {storage.get('stale_count', 0)} 个、"
            f"大文件 {storage.get('large_count', 0)} 个、"
            f"临时 {storage.get('temp_count', 0)} 个、"
            f"空目录 {storage.get('empty_dir_count', 0)} 个\n\n"
            f"重复：{len(report.get('duplicates', []))} 组\n"
            f"归档建议：{len(archive.get('stale_files', []))} 个过期文件，"
            f"预计释放 {archive.get('estimated_savings_mb', 0):.1f} MB"
        )
        self.app.after_ui(lambda: self.info("诊断报告", summary))
        self.app.after_ui(lambda: self.set_status("诊断完成"))

    # ── 生命周期 ──────────────────────────────────────────────

    def on_folder_changed(self) -> None:
        self.tree.clear()
        self.summary_var.set("选择文件夹后点击「预览整理」")
        self.empty.place(in_=self.tree.master, relx=0.5, rely=0.5, anchor=tk.CENTER)

    def refresh(self) -> None:
        if self.app.selected_folder.get():
            self.preview()
