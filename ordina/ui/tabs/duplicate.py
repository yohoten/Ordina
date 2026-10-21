"""
Tab · 查重
==========
按「大小分组 → MD5 校验」找出重复文件，树形展示、⭐ 标记建议保留项、可批量删除。
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..theme import FONTS
from ..widgets import (
    SortableTreeview, attach_scrollbar, button, card, empty_state,
    format_size, label, status_label,
)
from .base import BaseTab


class DuplicateTab(BaseTab):
    title = "查重"
    icon = "🔁"

    def build(self) -> None:
        # ── 顶部操作区 ──
        top = card(self, self.theme, "扫描操作")
        top.master.pack(fill=tk.X, padx=10, pady=(10, 6))

        actions = tk.Frame(top)
        self.theme.track(actions, bg="surface")
        actions.pack(fill=tk.X)

        button(actions, self.theme, "扫描重复文件", self.scan, "accent").pack(side=tk.LEFT, padx=(0, 6))
        button(actions, self.theme, "选中所有重复项", self.select_duplicates, "warning").pack(side=tk.LEFT, padx=(0, 6))
        button(actions, self.theme, "删除选中", self.delete_selected, "danger").pack(side=tk.LEFT, padx=(0, 12))
        label(actions, self.theme, "保留每组第一项（⭐），其余可安全删除", "small", "fg_subtle").pack(side=tk.LEFT)

        self.stats_var = tk.StringVar(value="尚未扫描")
        status_label(top, self.theme, self.stats_var, "accent").pack(anchor=tk.W, pady=(8, 0))

        # ── 结果树 ──
        body = card(self, self.theme, "重复文件")
        body.master.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tree = ttk.Treeview(
            body, columns=("path", "size", "md5"), show="tree headings",
            selectmode="extended", height=16,
        )
        self.tree.heading("#0", text="组 / 文件", anchor=tk.W)
        self.tree.heading("path", text="路径", anchor=tk.W)
        self.tree.heading("size", text="大小", anchor=tk.E)
        self.tree.heading("md5", text="MD5（前 8 位）", anchor=tk.CENTER)
        self.tree.column("#0", width=260, stretch=False)
        self.tree.column("path", width=420, anchor=tk.W)
        self.tree.column("size", width=100, anchor=tk.E, stretch=False)
        self.tree.column("md5", width=120, anchor=tk.CENTER, stretch=False)
        self.tree.tag_configure("group", background=self.theme.color("tree_head_bg"),
                                font=FONTS["body_bold"])
        self.tree.tag_configure("keep", foreground=self.theme.color("success"))
        self.tree.tag_configure("dupe", foreground=self.theme.color("danger"))
        self.theme.add_hook(self._repaint_tags)
        self.tree.bind("<Double-1>", self._open_file)

        scrollbar = attach_scrollbar(self.tree, self.theme)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._file_map: dict = {}
        self.empty = empty_state(body, self.theme, "🔁", "尚未扫描重复文件",
                                 "点击上方「扫描重复文件」开始检测")
        self.empty.place(in_=body, relx=0.5, rely=0.5, anchor=tk.CENTER)

    def _repaint_tags(self) -> None:
        self.tree.tag_configure("group", background=self.theme.color("tree_head_bg"))
        self.tree.tag_configure("keep", foreground=self.theme.color("success"))
        self.tree.tag_configure("dupe", foreground=self.theme.color("danger"))

    # ── 扫描 ──────────────────────────────────────────────────

    def scan(self) -> None:
        organizer = self.app.ensure_organizer()
        if organizer is None:
            return
        self.stats_var.set("正在扫描…")
        self.run_async(self._do_scan)

    def _do_scan(self) -> None:
        organizer = self.app.get_organizer()
        try:
            duplicates = organizer.find_duplicates()
        except Exception as exc:
            self.app.after_ui(lambda: self.error("扫描失败", str(exc)))
            return
        self.app.after_ui(lambda: self._render(duplicates))

    def _render(self, duplicates) -> None:
        self.tree.delete(*self.tree.get_children())
        self._file_map = {}

        groups = 0
        total_files = 0
        wasted = 0

        for index, group in enumerate(duplicates, 1):
            files = group.get("files", [])
            if len(files) < 2:
                continue
            groups += 1
            size = group.get("size", 0)
            wasted += size * (len(files) - 1)
            size_text = format_size(size)

            parent = self.tree.insert(
                "", tk.END, text=f"第 {index} 组（{len(files)} 个）",
                values=("", size_text, (group.get("md5") or "")[:8]),
                open=True, tags=("group",),
            )

            for position, path in enumerate(files):
                path = Path(path)
                keep = position == 0
                try:
                    size_text = format_size(path.stat().st_size)
                except OSError:
                    size_text = "—"
                child = self.tree.insert(
                    parent, tk.END,
                    text=("⭐ " if keep else "   ") + path.name,
                    values=(str(path), size_text, ""),
                    tags=("keep" if keep else "dupe",),
                )
                self._file_map[child] = path
                total_files += 1

        self.empty.place_forget() if groups else self.empty.place(
            in_=self.tree.master, relx=0.5, rely=0.5, anchor=tk.CENTER)

        if groups:
            self.stats_var.set(
                f"{groups} 组重复 · {total_files} 个文件 · 可释放 {format_size(wasted)}"
            )
            self.set_status(f"扫描完成 — {groups} 组重复文件")
        else:
            self.stats_var.set("未发现重复文件")
            self.set_status("扫描完成 — 未发现重复文件")

    # ── 选择 / 删除 ───────────────────────────────────────────

    def select_duplicates(self) -> None:
        for group_item in self.tree.get_children():
            children = self.tree.get_children(group_item)
            for child in children[1:]:
                self.tree.selection_add(child)
        self.set_status("已选中所有重复项（每组第一项保留）")

    def delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            self.warn("提示", "请先选择要删除的文件。")
            return
        if not self.ask_yes("确认删除",
                            f"将删除 {len(selected)} 个文件，此操作不可撤销。\n\n是否继续？"):
            return

        deleted, errors = 0, []
        for item in selected:
            path = self._file_map.get(item)
            if not path:
                continue
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                errors.append(f"{path.name}: {exc}")

        message = f"已删除 {deleted} 个文件"
        if errors:
            message += f"，{len(errors)} 个失败"
        self.info("完成", message)
        self.set_status(message)
        if deleted:
            self.scan()

    def _open_file(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        path = self._file_map.get(item)
        if path and path.exists():
            try:
                import os
                os.startfile(str(path))
            except Exception:
                pass

    # ── 生命周期 ──────────────────────────────────────────────

    def on_folder_changed(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._file_map = {}
        self.stats_var.set("尚未扫描")
        self.empty.place(in_=self.tree.master, relx=0.5, rely=0.5, anchor=tk.CENTER)

    def refresh(self) -> None:
        if self.app.selected_folder.get():
            self.scan()
