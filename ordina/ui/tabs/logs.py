"""
Tab · 日志
==========
读取目标目录下的 .ordina_logs / .organizer_logs，支持级别过滤、关键词搜索、自动刷新。
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..theme import FONTS, themed_scrolled_text
from ..widgets import button, card, label, status_label
from .base import BaseTab

LOG_DIR_NAMES = (".ordina_logs", ".organizer_logs")


class LogsTab(BaseTab):
    title = "日志"
    icon = "📝"

    def build(self) -> None:
        top = card(self, self.theme, "日志操作")
        top.master.pack(fill=tk.X, padx=10, pady=(10, 6))

        actions = tk.Frame(top)
        self.theme.track(actions, bg="surface")
        actions.pack(fill=tk.X)

        button(actions, self.theme, "刷新  F5", self.refresh_logs, "accent").pack(side=tk.LEFT, padx=(0, 6))
        button(actions, self.theme, "清除显示", self.clear_logs, "warning").pack(side=tk.LEFT, padx=(0, 12))

        self.auto_refresh_var = tk.BooleanVar(value=False)
        auto = tk.Checkbutton(actions, text="自动刷新（5 秒）", variable=self.auto_refresh_var,
                              font=FONTS["body"], cursor="hand2", borderwidth=0,
                              highlightthickness=0, command=self._toggle_auto_refresh)
        self.theme.track(auto, bg="surface", fg="fg_muted", selectcolor="entry_bg",
                         activebackground="surface", activeforeground="fg")
        auto.pack(side=tk.LEFT)

        label(actions, self.theme, "级别", "small", "fg_muted").pack(side=tk.LEFT, padx=(16, 4))
        self.level_var = tk.StringVar(value="ALL")
        level = ttk.Combobox(actions, textvariable=self.level_var, state="readonly",
                             values=["ALL", "INFO", "WARNING", "ERROR"], width=10)
        level.pack(side=tk.LEFT)
        level.bind("<<ComboboxSelected>>", lambda _e: self.refresh_logs())

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(actions, textvariable=self.search_var, width=16)
        search_entry.pack(side=tk.RIGHT)
        search_entry.bind("<Return>", lambda _e: self.search_logs())
        button(actions, self.theme, "查找", self.search_logs, "default").pack(side=tk.RIGHT, padx=(0, 6))

        body = card(self, self.theme, "操作历史")
        body.master.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.text = themed_scrolled_text(body, self.theme)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.insert(tk.END, "选择文件夹后可查看整理操作日志。\n")

        self.summary_var = tk.StringVar(value="")
        status_label(body, self.theme, self.summary_var).pack(anchor=tk.W, pady=(6, 0))

    # ── 刷新 ──────────────────────────────────────────────────

    def _log_dir(self) -> Path | None:
        folder = self.app.selected_folder.get()
        if not folder:
            return None
        base = Path(folder)
        for name in LOG_DIR_NAMES:
            candidate = base / name
            if candidate.is_dir():
                return candidate
        return None

    def refresh_logs(self) -> None:
        log_dir = self._log_dir()
        self.text.delete("1.0", tk.END)

        if log_dir is None:
            self.text.insert(tk.END, "暂无日志：请先选择文件夹并执行一次整理。\n")
            self.summary_var.set("")
            return

        log_files = sorted(log_dir.glob("*.log"), reverse=True)[:10]
        if not log_files:
            self.text.insert(tk.END, f"暂无日志文件（{log_dir.name}）\n")
            self.summary_var.set("")
            return

        level = self.level_var.get()
        for log_file in log_files:
            self.text.insert(tk.END, f"── {log_file.name} ──\n")
            try:
                content = log_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                self.text.insert(tk.END, "（读取失败）\n\n")
                continue
            if level != "ALL":
                content = "\n".join(line for line in content.splitlines()
                                    if level in line.upper())
            self.text.insert(tk.END, content + "\n\n")

        self.summary_var.set(f"显示 {len(log_files)} 个日志文件 · 来自 {log_dir.name}")
        self.set_status("日志已刷新")

    def clear_logs(self) -> None:
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, "（显示已清除，磁盘上的日志文件未删除）\n")
        self.set_status("日志显示已清除")

    def search_logs(self) -> None:
        query = self.search_var.get().strip()
        self.text.tag_remove("match", "1.0", tk.END)
        if not query:
            return
        self.text.tag_configure("match", background=self.theme.color("warning"),
                                foreground=self.theme.color("on_accent"))
        start, count = "1.0", 0
        while True:
            position = self.text.search(query, start, stopindex=tk.END, nocase=True)
            if not position:
                break
            end = f"{position}+{len(query)}c"
            self.text.tag_add("match", position, end)
            start = end
            count += 1
        self.set_status(f"找到 {count} 处匹配" if count else f"未找到：{query}")

    def _toggle_auto_refresh(self) -> None:
        if self.auto_refresh_var.get():
            self._schedule()
            self.set_status("日志自动刷新已开启")
        else:
            self.set_status("日志自动刷新已关闭")

    def _schedule(self) -> None:
        if not self.auto_refresh_var.get():
            return
        try:
            self.refresh_logs()
        except Exception:
            pass
        self.after(5000, self._schedule)

    # ── 生命周期 ──────────────────────────────────────────────

    def on_folder_changed(self) -> None:
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, "选择文件夹后可查看整理操作日志。\n")
        self.summary_var.set("")

    def refresh(self) -> None:
        self.refresh_logs()
