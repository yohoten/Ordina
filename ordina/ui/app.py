"""
主窗口 (Ordina / 归序)
======================
工具栏（品牌 + 目标文件夹 + 分类模式 + 主题开关）
    └ 标签页（整理 / 查重 / 分析 / 规则 / 日志）
状态栏（状态提示 + 主题指示 + 快捷键）
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import __app_name__, __app_name_cn__, __version__
from ..core import FileOrganizer, NameNormalizer, NamingRules
from .theme import FONTS, ThemeManager
from .widgets import SegmentedControl, button, label, status_label
from .tabs import TAB_CLASSES

CONFIG_PATH = Path.home() / ".ordina.json"
ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "icon.ico"

SHORTCUT_HINT = "Ctrl+O 打开  |  Ctrl+P 预览  |  Ctrl+Enter 执行  |  F5 刷新  |  Ctrl+T 主题"


class OrdinaApp:
    """应用主控制器：持有状态、组装界面、向标签页提供公共服务"""

    def __init__(self, root: tk.Tk, theme_name: str = "dark"):
        self.root = root
        root.title(f"{__app_name__} · {__app_name_cn__}  v{__version__}")
        root.geometry("1260x860")
        root.minsize(1000, 680)

        # ── 状态 ──
        self.selected_folder = tk.StringVar()
        self.mode = tk.StringVar(value="purpose")
        self.naming_rules = NamingRules()
        self.status_var = tk.StringVar(value=f"就绪 — {SHORTCUT_HINT}")
        self._organizer: FileOrganizer | None = None
        self._busy = False

        # ── 主题（先建，后续控件全部登记）──
        self.theme = ThemeManager(root, theme_name)
        self.theme.apply()

        self._set_icon()
        self._build_toolbar()
        self._build_notebook()
        self._build_status_bar()
        self._bind_shortcuts()

        self._load_config()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ═══════════════════════════════════════════════════════════
    # 界面组装
    # ═══════════════════════════════════════════════════════════

    def _set_icon(self) -> None:
        if ICON_PATH.exists():
            try:
                self.root.iconbitmap(str(ICON_PATH))
            except Exception:
                pass
        try:
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID("Ordina.FileOrganizer.3")
        except Exception:
            pass

    def _build_toolbar(self) -> None:
        toolbar = tk.Frame(self.root, height=60)
        self.theme.track(toolbar, bg="surface")
        toolbar.pack(fill=tk.X, side=tk.TOP)
        toolbar.pack_propagate(False)

        inner = tk.Frame(toolbar)
        self.theme.track(inner, bg="surface")
        inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        # 品牌区
        brand = tk.Frame(inner)
        self.theme.track(brand, bg="surface")
        brand.pack(side=tk.LEFT)
        label(brand, self.theme, "🗂", "title", "accent").pack(side=tk.LEFT, padx=(0, 8))
        titles = tk.Frame(brand)
        self.theme.track(titles, bg="surface")
        titles.pack(side=tk.LEFT)
        label(titles, self.theme, f"{__app_name__} · {__app_name_cn__}",
              "subtitle", "fg").pack(anchor=tk.W)
        label(titles, self.theme, f"按用途分类 · PC + 安卓双端 · v{__version__}",
              "small", "fg_subtle").pack(anchor=tk.W)

        # 路径区
        path_frame = tk.Frame(inner)
        self.theme.track(path_frame, bg="surface")
        path_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(24, 16))

        entry_shell = tk.Frame(path_frame, highlightthickness=1)
        self.theme.track(entry_shell, bg="entry_bg", highlightbackground="border")
        entry_shell.pack(fill=tk.X)

        self.folder_entry = tk.Entry(entry_shell, textvariable=self.selected_folder,
                                     font=FONTS["body"], relief=tk.FLAT, bd=0,
                                     highlightthickness=0)
        self.theme.track(self.folder_entry, bg="entry_bg", fg="fg",
                         insertbackground="fg", selectbackground="accent_soft",
                         selectforeground="fg")
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=10)
        self.folder_entry.bind("<Return>", lambda _e: self._on_folder_committed())

        button(entry_shell, self.theme, "浏览", self.select_folder, "accent").pack(side=tk.RIGHT, padx=4)

        # 模式 + 主题
        controls = tk.Frame(inner)
        self.theme.track(controls, bg="surface")
        controls.pack(side=tk.RIGHT)

        self.mode_switch = SegmentedControl(
            controls, self.theme,
            options=(("purpose", "用途分类"), ("extension", "扩展名")),
            variable=self.mode, command=self._on_mode_changed,
        )
        self.mode_switch.pack(side=tk.LEFT, padx=(0, 10))

        self.theme_btn = button(controls, self.theme, self._theme_icon(),
                                self.toggle_theme, "default")
        self.theme_btn.configure(width=4, font=FONTS["body"])
        self.theme_btn.pack(side=tk.LEFT)

    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 6))

        self.tabs = {}
        for index, tab_class in enumerate(TAB_CLASSES):
            instance = tab_class(self.notebook, self)
            self.notebook.add(instance, text=f"  {tab_class.icon} {tab_class.title}  ")
            self.tabs[index] = instance

    def _build_status_bar(self) -> None:
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, side=tk.BOTTOM)

        bar = tk.Frame(self.root, height=30)
        self.theme.track(bar, bg="status_bg")
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        status_label(bar, self.theme, self.status_var, "fg_muted").pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12)

        self.theme_indicator = tk.StringVar(value=self._theme_name())
        status_label(bar, self.theme, self.theme_indicator, "fg_subtle").pack(side=tk.RIGHT, padx=(0, 12))

        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.progress.pack(side=tk.RIGHT, padx=(0, 8))

    def _bind_shortcuts(self) -> None:
        bindings = {
            "<Control-o>": lambda _e: self.select_folder(),
            "<Control-p>": lambda _e: self._current_tab_action("preview"),
            "<Control-Return>": lambda _e: self._current_tab_action("execute"),
            "<F5>": lambda _e: self.refresh_current_tab(),
            "<Control-t>": lambda _e: self.toggle_theme(),
        }
        for key, handler in bindings.items():
            self.root.bind(key, handler)

        for index in range(len(TAB_CLASSES)):
            self.root.bind(f"<Control-Key-{index + 1}>",
                           lambda _e, i=index: self.notebook.select(i))

    # ═══════════════════════════════════════════════════════════
    # 公共服务（供标签页调用）
    # ═══════════════════════════════════════════════════════════

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def after_ui(self, func) -> None:
        """从工作线程安全地在主线程执行 UI 更新"""
        self.root.after(0, func)

    def info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self.root)

    def warn(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message, parent=self.root)

    def error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self.root)

    def ask_yes(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message, parent=self.root)

    def get_normalizer(self) -> NameNormalizer:
        return NameNormalizer(rules=self.naming_rules)

    def get_organizer(self) -> FileOrganizer | None:
        folder = self.selected_folder.get().strip()
        if not folder:
            return None
        if self._organizer is None or \
                str(self._organizer.download_folder) != str(Path(folder)) or \
                self._organizer.mode != self.mode.get() or \
                self._organizer.normalizer.rules != self.naming_rules:
            self._organizer = FileOrganizer(
                download_folder=folder,
                mode=self.mode.get(),
                naming_rules=self.naming_rules,
                verbose=False,
            )
        return self._organizer

    def rebuild_organizer(self) -> None:
        """命名规则/模式变化后丢弃缓存实例"""
        self._organizer = None

    def ensure_organizer(self) -> FileOrganizer | None:
        if not self.selected_folder.get().strip():
            self.warn("提示", "请先选择要整理的目标文件夹（Ctrl+O）。")
            return None
        try:
            return self.get_organizer()
        except Exception as exc:
            self.error("错误", f"无法初始化整理引擎：{exc}")
            return None

    def run_async(self, func, *args) -> None:
        """后台执行耗时任务，期间显示不确定进度条"""

        def worker():
            try:
                func(*args)
            except Exception as exc:  # 兜底，避免线程静默崩溃
                self.after_ui(lambda: self.error("任务失败", str(exc)))
            finally:
                self.after_ui(self._stop_progress)

        self._start_progress()
        threading.Thread(target=worker, daemon=True).start()

    def _start_progress(self) -> None:
        self._busy = True
        try:
            self.progress.start(12)
        except Exception:
            pass

    def _stop_progress(self) -> None:
        self._busy = False
        try:
            self.progress.stop()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # 事件
    # ═══════════════════════════════════════════════════════════

    def select_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择要整理的文件夹", parent=self.root)
        if not folder:
            return
        self.selected_folder.set(folder)
        self._on_folder_committed()

    def _on_folder_committed(self) -> None:
        folder = self.selected_folder.get().strip()
        if not folder or not Path(folder).is_dir():
            self.warn("提示", "文件夹不存在，请重新选择。")
            return
        self.rebuild_organizer()
        for tab in self.tabs.values():
            try:
                tab.on_folder_changed()
            except Exception:
                pass
        self.set_status(f"目标文件夹：{folder}")

    def _on_mode_changed(self, mode: str) -> None:
        self.rebuild_organizer()
        self.set_status(f"分类模式：{'用途分类' if mode == 'purpose' else '扩展名分类'}")

    def _current_tab_action(self, action: str) -> None:
        tab = self.tabs.get(self.notebook.index(self.notebook.select()))
        handler = getattr(tab, action, None) if tab else None
        if handler:
            handler()

    def refresh_current_tab(self) -> None:
        index = self.notebook.index(self.notebook.select())
        tab = self.tabs.get(index)
        if tab:
            tab.refresh()

    def toggle_theme(self) -> None:
        self.theme.toggle()
        self.theme_btn.configure(text=self._theme_icon())
        self.theme_indicator.set(self._theme_name())
        self.set_status(f"已切换到{self._theme_name()}主题")

    def _theme_icon(self) -> str:
        return "☀" if self.theme.is_dark else "☾"

    def _theme_name(self) -> str:
        return "暗色" if self.theme.is_dark else "亮色"

    # ═══════════════════════════════════════════════════════════
    # 配置持久化
    # ═══════════════════════════════════════════════════════════

    def _load_config(self) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        folder = config.get("last_folder", "")
        if folder and Path(folder).is_dir():
            self.selected_folder.set(folder)

        theme_name = config.get("theme", "dark")
        if theme_name in ("dark", "light"):
            self.theme.set(theme_name)
            self.theme_btn.configure(text=self._theme_icon())
            self.theme_indicator.set(self._theme_name())

        mode = config.get("mode", "purpose")
        self.mode.set(mode if mode in ("purpose", "extension") else "purpose")

        rules = config.get("naming_rules")
        if isinstance(rules, dict):
            self.naming_rules = NamingRules.from_dict(rules)

    def _save_config(self) -> None:
        payload = {
            "last_folder": self.selected_folder.get(),
            "theme": self.theme.name,
            "mode": self.mode.get(),
            "naming_rules": self.naming_rules.to_dict(),
        }
        try:
            CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        except Exception:
            pass

    def on_close(self) -> None:
        self._save_config()
        self.root.destroy()


def launch() -> int:
    """GUI 启动入口"""
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    OrdinaApp(root)
    root.mainloop()
    return 0
