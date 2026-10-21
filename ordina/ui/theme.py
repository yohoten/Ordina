"""
主题系统 (Ordina UI)
====================

旧版的问题：主题切换只重配 ttk 样式，工具栏、卡片、按钮、状态栏这些 tk 原生控件
颜色写死在构造参数里，切换后纹丝不动 ——「双主题」实际只生效了一半。

本模块的做法：
    1. `ThemeManager` 维护调色板（PALETTES）与「控件注册表」
    2. 所有自建控件在构造时通过 `theme.track(widget, bg="surface", fg="fg")` 登记
    3. 切换主题时统一重绘 ttk 样式 + 重配所有登记过的 tk 控件 + 触发回调（重绘画布等）
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

# ── 字体 ──────────────────────────────────────────────────────
UI_FONT = "Microsoft YaHei UI"
MONO_FONT = "Consolas"

FONTS: Dict[str, tuple] = {
    "title": (UI_FONT, 14, "bold"),
    "subtitle": (UI_FONT, 11, "bold"),
    "body": (UI_FONT, 9),
    "body_bold": (UI_FONT, 9, "bold"),
    "small": (UI_FONT, 8),
    "mono": (MONO_FONT, 10),
    "mono_small": (MONO_FONT, 9),
}

# ── 调色板 ────────────────────────────────────────────────────
DARK: Dict[str, str] = {
    "bg": "#16181D",
    "surface": "#1E2128",
    "surface_alt": "#252932",
    "surface_hover": "#2C313B",
    "border": "#31363F",
    "fg": "#E6E9EF",
    "fg_muted": "#9AA3B2",
    "fg_subtle": "#6E7681",
    "accent": "#4C8DFF",
    "accent_hover": "#6BA1FF",
    "accent_soft": "#1F3A66",
    "on_accent": "#FFFFFF",
    "success": "#3FB950",
    "success_hover": "#4AC45C",
    "warning": "#D29922",
    "warning_hover": "#E0A92E",
    "danger": "#F85149",
    "danger_hover": "#FF635B",
    "info": "#58A6FF",
    "entry_bg": "#0F1115",
    "tree_bg": "#1A1D23",
    "tree_alt": "#20242C",
    "tree_head_bg": "#252932",
    "tree_select": "#26447E",
    "status_bg": "#12141A",
    "progress_trough": "#252932",
    "canvas_bg": "#1A1D23",
    "canvas_grid": "#2C313B",
    "chart": ["#4C8DFF", "#3FB950", "#D29922", "#F85149", "#A371F7",
              "#39C5CF", "#FF7B72", "#DB6D28", "#8B949E", "#F778BA"],
}

LIGHT: Dict[str, str] = {
    "bg": "#F4F6F9",
    "surface": "#FFFFFF",
    "surface_alt": "#F0F2F6",
    "surface_hover": "#E8EBF0",
    "border": "#DCE1E8",
    "fg": "#1F2328",
    "fg_muted": "#5C6773",
    "fg_subtle": "#8A93A0",
    "accent": "#0969DA",
    "accent_hover": "#0860CA",
    "accent_soft": "#DDEBFF",
    "on_accent": "#FFFFFF",
    "success": "#1A7F37",
    "success_hover": "#1B8C3E",
    "warning": "#9A6700",
    "warning_hover": "#A87500",
    "danger": "#CF222E",
    "danger_hover": "#DC2B37",
    "info": "#0969DA",
    "entry_bg": "#FFFFFF",
    "tree_bg": "#FFFFFF",
    "tree_alt": "#F7F9FC",
    "tree_head_bg": "#EEF1F6",
    "tree_select": "#CCE1FF",
    "status_bg": "#FFFFFF",
    "progress_trough": "#E5E9EF",
    "canvas_bg": "#FFFFFF",
    "canvas_grid": "#E5E9EF",
    "chart": ["#0969DA", "#1A7F37", "#9A6700", "#CF222E", "#8250DF",
              "#1B7C83", "#B3502A", "#6E4C1E", "#6E7781", "#BF3989"],
}

PALETTES: Dict[str, Dict[str, str]] = {"dark": DARK, "light": LIGHT}


class ThemeManager:
    """调色板 + 控件注册表 + ttk 样式，三者统一切换"""

    def __init__(self, root: tk.Misc, name: str = "dark"):
        self.root = root
        self.name = name if name in PALETTES else "dark"
        self.colors: Dict[str, object] = dict(PALETTES[self.name])
        self._tracked: List[tuple] = []
        self._hooks: List[Callable[[], None]] = []
        self._style = ttk.Style()

    # ── 基础 ──────────────────────────────────────────────────

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"

    def color(self, key: str, fallback: Optional[str] = None) -> str:
        """取色；key 不在调色板时按字面颜色返回（便于传固定色）"""
        return str(self.colors.get(key, fallback if fallback is not None else key))

    def toggle(self) -> str:
        self.set("light" if self.is_dark else "dark")
        return self.name

    def set(self, name: str) -> None:
        if name not in PALETTES:
            return
        self.name = name
        self.colors = dict(PALETTES[name])
        self.apply()

    # ── 注册 ──────────────────────────────────────────────────

    def track(self, widget: tk.Misc, **mapping: Optional[str]) -> tk.Misc:
        """
        登记控件并立即上色

        mapping 的键是控件选项名（bg / fg / activebackground ...），
        值是调色板键名；值不在调色板中时按字面颜色处理。
        """
        self._tracked.append((widget, mapping))
        self._paint(widget, mapping)
        return widget

    def untrack(self, widget: tk.Misc) -> None:
        self._tracked = [(w, m) for w, m in self._tracked if w is not widget]

    def add_hook(self, hook: Callable[[], None]) -> None:
        """主题变化时的回调（重绘画布、刷新 tree 标签等）"""
        self._hooks.append(hook)

    # ── 应用 ──────────────────────────────────────────────────

    def apply(self) -> None:
        self._configure_ttk()
        alive: List[tuple] = []
        for widget, mapping in self._tracked:
            try:
                if not widget.winfo_exists():
                    continue
            except Exception:
                continue
            self._paint(widget, mapping)
            alive.append((widget, mapping))
        self._tracked = alive

        for hook in list(self._hooks):
            try:
                hook()
            except Exception:
                pass

    def _paint(self, widget: tk.Misc, mapping: Dict[str, Optional[str]]) -> None:
        options = {}
        for option, key in mapping.items():
            if key is None:
                continue
            options[option] = self.color(key)
        if not options:
            return
        try:
            widget.configure(**options)
        except (tk.TclError, AttributeError):
            pass

    # ── ttk 样式 ──────────────────────────────────────────────

    def _configure_ttk(self) -> None:
        style = self._style
        c = self.colors

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=self.color("bg"), foreground=self.color("fg"),
                        fieldbackground=self.color("surface"),
                        troughcolor=self.color("progress_trough"),
                        bordercolor=self.color("border"),
                        lightcolor=self.color("surface"),
                        darkcolor=self.color("surface"),
                        font=FONTS["body"])

        style.configure("TFrame", background=self.color("bg"))
        style.configure("TLabel", background=self.color("bg"), foreground=self.color("fg"),
                        font=FONTS["body"])
        style.configure("Muted.TLabel", foreground=self.color("fg_muted"))
        style.configure("Subtle.TLabel", foreground=self.color("fg_subtle"), font=FONTS["small"])
        style.configure("Title.TLabel", font=FONTS["subtitle"], foreground=self.color("fg"))

        style.configure("TLabelframe", background=self.color("bg"),
                        bordercolor=self.color("border"), relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=self.color("bg"),
                        foreground=self.color("accent"), font=FONTS["body_bold"])

        style.configure("Card.TFrame", background=self.color("surface"), relief="flat")
        style.configure("TNotebook", background=self.color("bg"), borderwidth=0, tabmargins=(6, 4, 6, 0))
        style.configure("TNotebook.Tab", font=FONTS["body"], padding=(16, 8),
                        background=self.color("surface_alt"),
                        foreground=self.color("fg_muted"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", self.color("accent")), ("active", self.color("surface_hover"))],
                  foreground=[("selected", self.color("on_accent")), ("active", self.color("fg"))])

        # 按钮
        button_variants = (
            ("TButton", "surface_alt", "surface_hover", "fg"),
            ("Accent.TButton", "accent", "accent_hover", "on_accent"),
            ("Success.TButton", "success", "success_hover", "on_accent"),
            ("Warning.TButton", "warning", "warning_hover", "on_accent"),
            ("Danger.TButton", "danger", "danger_hover", "on_accent"),
            ("Ghost.TButton", "bg", "surface_alt", "fg"),
        )
        for variant, base, hover, fg_key in button_variants:
            text_color = self.color(fg_key)
            style.configure(variant, font=FONTS["body"], padding=(12, 6),
                            background=self.color(base), foreground=text_color,
                            borderwidth=0, relief="flat", focuscolor=self.color(base))
            style.map(variant,
                      background=[("active", self.color(hover)),
                                  ("disabled", self.color("surface_alt"))],
                      foreground=[("active", text_color),
                                  ("disabled", self.color("fg_subtle"))])

        style.configure("Toolbar.TButton", font=FONTS["body"], padding=(10, 5))

        # 输入
        style.configure("TEntry", fieldbackground=self.color("entry_bg"),
                        foreground=self.color("fg"), insertcolor=self.color("fg"),
                        bordercolor=self.color("border"), lightcolor=self.color("border"),
                        padding=(8, 5), relief="flat")
        style.map("TEntry", bordercolor=[("focus", self.color("accent"))],
                  lightcolor=[("focus", self.color("accent"))])
        style.configure("TCombobox", fieldbackground=self.color("entry_bg"),
                        foreground=self.color("fg"), background=self.color("surface"),
                        arrowcolor=self.color("fg_muted"), bordercolor=self.color("border"),
                        padding=(8, 5), relief="flat")
        style.map("TCombobox", fieldbackground=[("readonly", self.color("entry_bg"))],
                  foreground=[("readonly", self.color("fg"))],
                  bordercolor=[("focus", self.color("accent"))])

        style.configure("TCheckbutton", background=self.color("surface"),
                        foreground=self.color("fg"), font=FONTS["body"],
                        indicatorcolor=self.color("entry_bg"),
                        bordercolor=self.color("border"))
        style.map("TCheckbutton", background=[("active", self.color("surface"))],
                  indicatorcolor=[("selected", self.color("accent"))])
        style.configure("TRadiobutton", background=self.color("surface"),
                        foreground=self.color("fg"), font=FONTS["body"],
                        indicatorcolor=self.color("entry_bg"))
        style.map("TRadiobutton", indicatorcolor=[("selected", self.color("accent"))])

        # 表格
        style.configure("Treeview", font=FONTS["body"], rowheight=28,
                        background=self.color("tree_bg"), fieldbackground=self.color("tree_bg"),
                        foreground=self.color("fg"), bordercolor=self.color("border"),
                        relief="flat")
        style.configure("Treeview.Heading", font=FONTS["body_bold"],
                        background=self.color("tree_head_bg"), foreground=self.color("fg"),
                        bordercolor=self.color("border"), relief="flat", padding=(8, 6))
        style.map("Treeview",
                  background=[("selected", self.color("tree_select"))],
                  foreground=[("selected", self.color("fg"))])
        style.configure("TProgressbar", background=self.color("accent"),
                        troughcolor=self.color("progress_trough"), borderwidth=0, thickness=8)
        style.configure("TSeparator", background=self.color("border"))
        style.configure("TPanedwindow", background=self.color("bg"))
        style.configure("Sash", sashthickness=6, gripcount=0, background=self.color("bg"))

        # 滚动条
        for orient_name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(orient_name, background=self.color("surface_alt"),
                            troughcolor=self.color("bg"), borderwidth=0,
                            arrowcolor=self.color("fg_muted"), relief="flat")
            style.map(orient_name, background=[("active", self.color("surface_hover"))])


def themed_scrolled_text(parent: tk.Misc, theme: ThemeManager, **kwargs) -> tk.Text:
    """带主题登记的滚动文本框"""
    from tkinter import scrolledtext

    kwargs.setdefault("font", FONTS["mono"])
    kwargs.setdefault("wrap", tk.WORD)
    kwargs.setdefault("relief", "flat")
    kwargs.setdefault("borderwidth", 0)
    kwargs.setdefault("padx", 10)
    kwargs.setdefault("pady", 8)
    widget = scrolledtext.ScrolledText(parent, **kwargs)
    theme.track(widget, bg="entry_bg", fg="fg", insertbackground="fg",
                selectbackground="accent_soft", selectforeground="fg")
    return widget
