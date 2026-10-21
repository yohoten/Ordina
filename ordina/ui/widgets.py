"""
通用控件层 (Ordina UI)
======================

把旧版 gui.py 里重复了几十次的「手写 tk.LabelFrame + 手写 tk.Button + 手写配色」
抽成可复用控件：卡片、按钮（含悬停）、分段控件、可排序表格、键值行、空状态。
所有控件在构造时自动登记到主题管理器，主题切换时整体重绘。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .theme import FONTS, ThemeManager


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def format_size(size_bytes: float) -> str:
    """字节 → 人类可读"""
    size = float(size_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024.0:
            return f"{size:.2f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


# ═══════════════════════════════════════════════════════════════
# 卡片
# ═══════════════════════════════════════════════════════════════

def card(parent: tk.Misc,
         theme: ThemeManager,
         title: str = "",
         padx: int = 14,
         pady: int = 12) -> tk.Frame:
    """
    圆角观感的分组容器（用 border + 内边距模拟），带标题行

    返回「内容区」Frame，调用方往里塞控件即可。
    """
    outer = tk.Frame(parent, highlightthickness=1, padx=padx, pady=pady)
    theme.track(outer, bg="surface", highlightbackground="border")

    if title:
        header = tk.Frame(outer)
        theme.track(header, bg="surface")
        header.pack(fill=tk.X, pady=(0, 8))
        theme.track(tk.Label(header, text=title, font=FONTS["subtitle"],
                             anchor=tk.W), bg="surface", fg="fg").pack(side=tk.LEFT)
        theme.track(tk.Frame(header, height=1), bg="border").pack(fill=tk.X, pady=(6, 0))

    body = tk.Frame(outer)
    theme.track(body, bg="surface")
    body.pack(fill=tk.BOTH, expand=True)
    return body


def card_container(parent: tk.Misc, theme: ThemeManager, **pack_kw) -> tk.Frame:
    """无标题卡片容器（直接返回可 pack 的 Frame）"""
    outer = tk.Frame(parent, highlightthickness=1)
    theme.track(outer, bg="surface", highlightbackground="border")
    if pack_kw:
        outer.pack(**pack_kw)
    return outer


# ═══════════════════════════════════════════════════════════════
# 按钮
# ═══════════════════════════════════════════════════════════════

def button(parent: tk.Misc,
           theme: ThemeManager,
           text: str,
           command: Optional[Callable[[], None]] = None,
           variant: str = "default",
           width: Optional[int] = None,
           state: str = tk.NORMAL) -> tk.Button:
    """
    主题化按钮（tk.Button + 悬停态）

    variant: default / accent / success / warning / danger / ghost
    """
    variants = {
        "default": ("surface_alt", "surface_hover", "fg"),
        "accent": ("accent", "accent_hover", "on_accent"),
        "success": ("success", "success_hover", "on_accent"),
        "warning": ("warning", "warning_hover", "on_accent"),
        "danger": ("danger", "danger_hover", "on_accent"),
        "ghost": ("bg", "surface_alt", "fg"),
    }
    base_key, hover_key, fg_key = variants.get(variant, variants["default"])

    widget = tk.Button(
        parent, text=text, command=command, font=FONTS["body"],
        relief=tk.FLAT, borderwidth=0, cursor="hand2",
        padx=14, pady=6, state=state,
        activebackground=theme.color(hover_key), activeforeground=theme.color(fg_key),
    )
    if width:
        widget.configure(width=width)

    theme.track(widget, bg=base_key, fg=fg_key)
    _bind_hover(widget, theme, base_key, hover_key)
    return widget


def _bind_hover(widget: tk.Button, theme: ThemeManager,
                base_key: str, hover_key: str) -> None:
    """悬停变色（tk.Button 没有 hover 样式，只能手动绑）"""
    def enter(_event=None):
        if str(widget.cget("state")) == tk.DISABLED:
            return
        widget.configure(bg=theme.color(hover_key))

    def leave(_event=None):
        if str(widget.cget("state")) == tk.DISABLED:
            return
        widget.configure(bg=theme.color(base_key))

    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)
    # 主题切换后需要能恢复基色
    theme.add_hook(leave)


def ttk_button(parent: tk.Misc, text: str, command=None,
               variant: str = "TButton", width: Optional[int] = None) -> ttk.Button:
    """ttk 按钮（自带 hover 映射，用于表格工具栏等轻量场景）"""
    widget = ttk.Button(parent, text=text, command=command, style=variant)
    if width:
        widget.configure(width=width)
    return widget


# ═══════════════════════════════════════════════════════════════
# 分段控件（模式切换）
# ═══════════════════════════════════════════════════════════════

class SegmentedControl(tk.Frame):
    """小巧的分段切换器，替代旧版两个互斥按钮的手写联动"""

    def __init__(self,
                 master: tk.Misc,
                 theme: ThemeManager,
                 options: Sequence[Tuple[str, str]],
                 variable: tk.StringVar,
                 command: Optional[Callable[[str], None]] = None):
        super().__init__(master)
        self.theme = theme
        self.options = list(options)
        self.variable = variable
        self.command = command
        self._buttons: Dict[str, tk.Button] = {}

        theme.track(self, bg="surface")
        for value, label_text in self.options:
            btn = tk.Button(self, text=label_text, font=FONTS["body"], relief=tk.FLAT,
                            borderwidth=0, cursor="hand2", padx=12, pady=4,
                            command=lambda v=value: self.select(v))
            btn.pack(side=tk.LEFT, padx=(0, 2))
            self._buttons[value] = btn

        self._paint()
        variable.trace_add("write", lambda *_: self._paint())
        theme.add_hook(self._paint)

    def select(self, value: str) -> None:
        if self.variable.get() == value:
            return
        self.variable.set(value)
        self._paint()
        if self.command:
            self.command(value)

    def _paint(self) -> None:
        """按当前取值上色（选中段用强调色）"""
        current = self.variable.get()
        for value, btn in self._buttons.items():
            selected = value == current
            btn.configure(
                bg=self.theme.color("accent" if selected else "surface_alt"),
                fg=self.theme.color("on_accent" if selected else "fg_muted"),
                activebackground=self.theme.color("accent_hover" if selected else "surface_hover"),
                activeforeground=self.theme.color("on_accent" if selected else "fg"),
                font=FONTS["body_bold" if selected else "body"],
            )


# ═══════════════════════════════════════════════════════════════
# 标签 / 文本
# ═══════════════════════════════════════════════════════════════

def label(parent: tk.Misc, theme: ThemeManager, text: str,
          style: str = "body", color: str = "fg", bg: str = "surface",
          **pack_kw) -> tk.Label:
    widget = tk.Label(parent, text=text, font=FONTS.get(style, FONTS["body"]))
    theme.track(widget, bg=bg, fg=color)
    if pack_kw:
        widget.pack(**pack_kw)
    return widget


def status_label(parent: tk.Misc, theme: ThemeManager,
                 textvariable: tk.StringVar, color: str = "fg_muted",
                 bg: str = "surface") -> tk.Label:
    widget = tk.Label(parent, textvariable=textvariable, font=FONTS["small"], anchor=tk.W)
    theme.track(widget, bg=bg, fg=color)
    return widget


# ═══════════════════════════════════════════════════════════════
# 可排序表格
# ═══════════════════════════════════════════════════════════════

class SortableTreeview(ttk.Treeview):
    """点表头排序的 Treeview（数值/文本自动识别，斑马纹）"""

    def __init__(self, master: tk.Misc, theme: ThemeManager,
                 columns: Sequence[Tuple[str, str, int, str]],
                 sortable: Optional[Iterable[str]] = None, **kwargs):
        """
        columns: [(列名, 标题, 宽度, anchor), ...]
        sortable: 可排序列名集合，默认全部
        """
        names = [c[0] for c in columns]
        show = kwargs.pop("show", "headings")
        height = kwargs.pop("height", 14)
        super().__init__(master, columns=names, show=show, height=height, **kwargs)

        self.theme = theme
        self._sort_state: Dict[str, bool] = {}
        self._sortable = set(sortable) if sortable else set(names)

        for name, heading, width, anchor in columns:
            self.heading(name, text=heading, anchor=anchor,
                         command=lambda n=name: self.sort_by(n))
            stretch = width > 0
            self.column(name, width=abs(width), anchor=anchor,
                        stretch=stretch, minwidth=60)

        self.tag_configure("odd", background=theme.color("tree_bg"))
        self.tag_configure("even", background=theme.color("tree_alt"))
        theme.add_hook(self._repaint_tags)

    # ── 排序 ──

    @staticmethod
    def _sort_key(value: str):
        text = str(value).replace(",", "").strip()
        try:
            return (0, float(text.split()[0]) if text else 0.0)
        except (ValueError, IndexError):
            return (1, text.lower())

    def sort_by(self, column: str, descending: Optional[bool] = None) -> None:
        if column not in self._sortable:
            return
        if descending is None:
            descending = not self._sort_state.get(column, False)
        self._sort_state[column] = descending

        rows = [(self.set(child, column), child) for child in self.get_children("")]
        rows.sort(key=lambda item: self._sort_key(item[0]), reverse=descending)
        for index, (_, child) in enumerate(rows):
            self.move(child, "", index)
        self._restripe()

    def _restripe(self) -> None:
        for index, child in enumerate(self.get_children("")):
            existing = [t for t in self.item(child, "tags") if t not in ("odd", "even")]
            existing.append("odd" if index % 2 == 0 else "even")
            self.item(child, tags=tuple(existing))

    def _repaint_tags(self) -> None:
        self.tag_configure("odd", background=self.theme.color("tree_bg"))
        self.tag_configure("even", background=self.theme.color("tree_alt"))

    def insert_row(self, values: Sequence, tags: Sequence[str] = ()) -> str:
        item = self.insert("", tk.END, values=tuple(values), tags=tuple(tags))
        self._restripe()
        return item

    def clear(self) -> None:
        self.delete(*self.get_children())


def attach_scrollbar(tree: ttk.Treeview, theme: ThemeManager) -> ttk.Scrollbar:
    scrollbar = ttk.Scrollbar(tree.master, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    return scrollbar


# ═══════════════════════════════════════════════════════════════
# 空状态 / 键值行
# ═══════════════════════════════════════════════════════════════

def empty_state(parent: tk.Misc, theme: ThemeManager,
                icon: str, title: str, hint: str = "") -> tk.Frame:
    """空数据占位，避免界面一片空白"""
    frame = tk.Frame(parent)
    theme.track(frame, bg="surface")
    theme.track(tk.Label(frame, text=icon, font=(FONTS["mono"][0], 28)),
                bg="surface", fg="fg_subtle").pack(pady=(10, 4))
    theme.track(tk.Label(frame, text=title, font=FONTS["body_bold"]),
                bg="surface", fg="fg_muted").pack()
    if hint:
        theme.track(tk.Label(frame, text=hint, font=FONTS["small"]),
                    bg="surface", fg="fg_subtle").pack(pady=(2, 10))
    return frame


def stat_row(parent: tk.Misc, theme: ThemeManager,
             key: str, value: str, value_color: str = "fg") -> tk.Frame:
    """「指标 : 数值」一行"""
    row = tk.Frame(parent)
    theme.track(row, bg="surface")
    theme.track(tk.Label(row, text=key, font=FONTS["body"], width=16, anchor=tk.W),
                bg="surface", fg="fg_muted").pack(side=tk.LEFT)
    theme.track(tk.Label(row, text=value, font=FONTS["body_bold"], anchor=tk.W),
                bg="surface", fg=value_color).pack(side=tk.LEFT, fill=tk.X, expand=True)
    return row
