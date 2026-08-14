"""
增强版多标签 GUI v3.0 — 全面布局重构
======================================
Tab 1 - 整理: Treeview 可排序预览 + 批量选择 + 进度条
Tab 2 - 查重: 树形展开/折叠 + 全选重复项 + 双击预览
Tab 3 - 分析: Canvas 可视化图表 + Treeview 统计表
Tab 4 - 规则: JSON 实时校验 + 导入/导出 + 搜索过滤
Tab 5 - 日志: 级别过滤 + 自动刷新 + 关键词搜索
全局: 暗色/亮色主题一键切换 + 快捷键支持
"""

import json
import os
import sys
import threading
import math
from pathlib import Path
from datetime import datetime

# 确保当前目录在 Python 路径中
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


# ═══════════════════════════════════════════════════════════════
# 主题管理器
# ═══════════════════════════════════════════════════════════════

class ThemeManager:
    """暗色/亮色双主题管理器"""

    LIGHT = {
        "name": "light",
        "bg": "#FAFAFA",
        "fg": "#333333",
        "card_bg": "#FFFFFF",
        "card_fg": "#333333",
        "primary": "#2196F3",
        "success": "#4CAF50",
        "warning": "#FF9800",
        "danger": "#F44336",
        "subtitle": "#666666",
        "border": "#E0E0E0",
        "tree_bg": "#FFFFFF",
        "tree_fg": "#333333",
        "tree_head_bg": "#F5F5F5",
        "tree_head_fg": "#333333",
        "text_bg": "#FAFAFA",
        "text_fg": "#333333",
        "progress_bg": "#E0E0E0",
        "canvas_bg": "#FFFFFF",
        "canvas_grid": "#E8E8E8",
        "chart_colors": ["#2196F3", "#4CAF50", "#FF9800", "#F44336",
                         "#9C27B0", "#00BCD4", "#FF5722", "#795548",
                         "#607D8B", "#E91E63"],
        "status_bg": "#F5F5F5",
        "status_fg": "#333333",
    }

    DARK = {
        "name": "dark",
        "bg": "#1E1E1E",
        "fg": "#D4D4D4",
        "card_bg": "#2D2D2D",
        "card_fg": "#E0E0E0",
        "primary": "#64B5F6",
        "success": "#81C784",
        "warning": "#FFB74D",
        "danger": "#E57373",
        "subtitle": "#999999",
        "border": "#404040",
        "tree_bg": "#252526",
        "tree_fg": "#CCCCCC",
        "tree_head_bg": "#333333",
        "tree_head_fg": "#E0E0E0",
        "text_bg": "#1E1E1E",
        "text_fg": "#D4D4D4",
        "progress_bg": "#404040",
        "canvas_bg": "#252526",
        "canvas_grid": "#404040",
        "chart_colors": ["#64B5F6", "#81C784", "#FFB74D", "#E57373",
                         "#CE93D8", "#4DD0E1", "#FF8A65", "#A1887F",
                         "#90A4AE", "#F06292"],
        "status_bg": "#2D2D2D",
        "status_fg": "#CCCCCC",
    }

    def __init__(self):
        self.current = "light"
        self.colors = self.LIGHT.copy()

    def toggle(self):
        self.current = "dark" if self.current == "light" else "light"
        self.colors = self.DARK if self.current == "dark" else self.LIGHT
        return self.current

    def is_dark(self):
        return self.current == "dark"


# ═══════════════════════════════════════════════════════════════
# 主 GUI 类
# ═══════════════════════════════════════════════════════════════

class EnhancedGUI:
    """增强版文件整理 GUI — v3.0 布局重构版"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("📁 下载文件夹整理工具 v3.0")
        self.root.geometry("1200x850")
        self.root.minsize(950, 650)

        # 主题
        self.theme = ThemeManager()

        # 设置应用图标
        self._set_app_icon()

        # 状态
        self.organizer = None
        self.selected_folder = tk.StringVar()
        self.mode = tk.StringVar(value="purpose")
        self.is_running = False
        self.auto_refresh_logs = tk.BooleanVar(value=False)
        self.log_filter_level = tk.StringVar(value="ALL")

        # 快捷键绑定
        self._bind_shortcuts()

        # 样式
        self._setup_styles()

        # 构建界面
        self._create_toolbar()       # 紧凑工具栏（替代原 header）
        self._create_notebook()
        self._create_status_bar()

        # 加载初始状态
        self._load_last_folder()

        # 窗口关闭
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── 应用图标 ────────────────────────────────────────────────

    def _set_app_icon(self):
        """设置窗口图标和任务栏图标"""
        ico_path = Path(__file__).parent / "download_organizer.ico"
        if ico_path.exists():
            try:
                # 设置窗口标题栏图标
                self.root.iconbitmap(str(ico_path))
                # Windows 任务栏图标
                try:
                    from ctypes import windll
                    windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                        "DownloadOrganizer.2.0"
                    )
                except Exception:
                    pass
            except Exception:
                pass

    # ── 快捷键 ──────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self._select_folder())
        self.root.bind("<Control-p>", lambda e: self._preview_organize())
        self.root.bind("<Control-Return>", lambda e: self._execute_organize())
        self.root.bind("<F5>", lambda e: self._refresh_current_tab())
        self.root.bind("<Control-t>", lambda e: self._toggle_theme())

    def _refresh_current_tab(self):
        tab_idx = self.notebook.index(self.notebook.select())
        if tab_idx == 1:
            self._scan_duplicates()
        elif tab_idx == 2:
            self._run_analysis()
        elif tab_idx == 4:
            self._refresh_logs()

    def _toggle_theme(self):
        self.theme.toggle()
        self._apply_theme()
        self._redraw_chart()

    # ── 主题应用 ────────────────────────────────────────────────

    def _apply_theme(self):
        c = self.theme.colors
        style = ttk.Style()

        # 全局背景
        self.root.configure(bg=c["bg"])

        style.configure(".", background=c["bg"], foreground=c["fg"])

        style.configure("TFrame", background=c["bg"])
        style.configure("TLabel", background=c["bg"], foreground=c["fg"])
        style.configure("TLabelframe", background=c["bg"], foreground=c["card_fg"])
        style.configure("TLabelframe.Label", background=c["bg"], foreground=c["primary"],
                       font=("微软雅黑", 11, "bold"))
        style.configure("Card.TLabelframe", background=c["card_bg"],
                       foreground=c["card_fg"], borderwidth=1, relief="solid")
        style.configure("Card.TLabelframe.Label", background=c["card_bg"],
                       foreground=c["primary"], font=("微软雅黑", 11, "bold"))

        style.configure("TNotebook", background=c["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", font=("微软雅黑", 10), padding=(18, 8),
                       background=c["card_bg"], foreground=c["fg"])
        style.map("TNotebook.Tab",
                 background=[("selected", c["primary"])],
                 foreground=[("selected", "#FFFFFF")])

        style.configure("TButton", font=("微软雅黑", 9), padding=(12, 6))
        style.configure("Primary.TButton", font=("微软雅黑", 9, "bold"),
                       padding=(12, 6))

        style.configure("Toolbar.TButton", font=("微软雅黑", 9), padding=(10, 5))

        style.configure("TEntry", fieldbackground=c["text_bg"],
                       foreground=c["text_fg"])
        style.configure("TCombobox", fieldbackground=c["text_bg"],
                       foreground=c["text_fg"])

        style.configure("Treeview", font=("微软雅黑", 9), rowheight=26,
                       background=c["tree_bg"], foreground=c["tree_fg"],
                       fieldbackground=c["tree_bg"])
        style.configure("Treeview.Heading", font=("微软雅黑", 9, "bold"),
                       background=c["tree_head_bg"], foreground=c["tree_head_fg"])
        style.map("Treeview", background=[("selected", c["primary"])],
                 foreground=[("selected", "#FFFFFF")])

        style.configure("TProgressbar", background=c["primary"],
                       troughcolor=c["progress_bg"])

        style.configure("Status.TLabel", font=("微软雅黑", 9),
                       foreground=c["status_fg"], padding=5)

        # 更新所有 ScrolledText 的颜色
        for widget_name in ["org_result", "analyze_result", "rules_text",
                           "kw_text", "logs_text"]:
            if hasattr(self, widget_name):
                widget = getattr(self, widget_name)
                widget.configure(bg=c["text_bg"], fg=c["text_fg"],
                               insertbackground=c["fg"])

    # ── 样式初始化 ──────────────────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        self._apply_theme()

    # ── 紧凑工具栏 ──────────────────────────────────────────────

    def _create_toolbar(self):
        """紧凑型 Ribbon 工具栏：标题 + 文件夹 + 模式 + 主题切换"""
        c = self.theme.colors
        toolbar = tk.Frame(self.root, bg=c["primary"], height=56)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        inner = tk.Frame(toolbar, bg=c["primary"])
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 左侧：Logo + 标题
        left_frame = tk.Frame(inner, bg=c["primary"])
        left_frame.pack(side=tk.LEFT)

        tk.Label(left_frame, text="📁", font=("Segoe UI Emoji", 20),
                bg=c["primary"]).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(left_frame, text="下载文件夹整理工具",
                font=("微软雅黑", 14, "bold"), fg="#FFFFFF",
                bg=c["primary"]).pack(side=tk.LEFT)
        tk.Label(left_frame, text="v3.0", font=("微软雅黑", 8),
                fg="#BBDEFB", bg=c["primary"]).pack(side=tk.LEFT, padx=(6, 0))

        # 中间：文件夹路径
        center_frame = tk.Frame(inner, bg=c["primary"])
        center_frame.pack(side=tk.LEFT, padx=(30, 0), fill=tk.X, expand=True)

        path_frame = tk.Frame(center_frame, bg="#FFFFFF", highlightthickness=0)
        path_frame.pack(fill=tk.X)

        self.folder_entry = tk.Entry(path_frame, textvariable=self.selected_folder,
                                     font=("Consolas", 10), relief=tk.FLAT,
                                     bg="#FFFFFF", fg="#333333",
                                     insertbackground="#333333",
                                     selectbackground=c["primary"],
                                     selectforeground="#FFFFFF")
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3, padx=(8, 0))

        browse_btn = tk.Button(path_frame, text="📂 浏览", font=("微软雅黑", 9),
                              bg=c["primary"], fg="#FFFFFF", relief=tk.FLAT,
                              activebackground=c["primary"],
                              activeforeground="#FFFFFF",
                              cursor="hand2", command=self._select_folder,
                              padx=14, pady=3)
        browse_btn.pack(side=tk.RIGHT)

        # 右侧：模式切换 + 主题按钮
        right_frame = tk.Frame(inner, bg=c["primary"])
        right_frame.pack(side=tk.RIGHT, padx=(0, 0))

        self.mode_btn_frame = tk.Frame(right_frame, bg=c["primary"])
        self.mode_btn_frame.pack(side=tk.LEFT, padx=(0, 12))

        self.purpose_btn = tk.Button(self.mode_btn_frame, text="🎨 用途分类",
                                    font=("微软雅黑", 9, "bold"),
                                    bg="#FFFFFF", fg=c["primary"],
                                    relief=tk.FLAT, padx=12, pady=3,
                                    cursor="hand2",
                                    command=lambda: self._switch_mode("purpose"))
        self.purpose_btn.pack(side=tk.LEFT)

        self.ext_btn = tk.Button(self.mode_btn_frame, text="📄 扩展名",
                                font=("微软雅黑", 9),
                                bg=c["primary"], fg="#FFFFFF",
                                relief=tk.FLAT, padx=12, pady=3,
                                cursor="hand2",
                                command=lambda: self._switch_mode("extension"))
        self.ext_btn.pack(side=tk.LEFT)

        theme_btn = tk.Button(right_frame, text="🌙" if not self.theme.is_dark() else "☀️",
                             font=("Segoe UI Emoji", 14),
                             bg=c["primary"], fg="#FFFFFF",
                             relief=tk.FLAT, cursor="hand2",
                             activebackground=c["primary"],
                             command=self._toggle_theme,
                             padx=6, pady=0)
        theme_btn.pack(side=tk.LEFT)
        self.theme_toggle_btn = theme_btn

    def _switch_mode(self, mode):
        """切换分类模式（工具栏按钮样式联动）"""
        self.mode.set(mode)
        c = self.theme.colors
        if mode == "purpose":
            self.purpose_btn.configure(bg="#FFFFFF", fg=c["primary"],
                                       font=("微软雅黑", 9, "bold"))
            self.ext_btn.configure(bg=c["primary"], fg="#FFFFFF",
                                   font=("微软雅黑", 9))
        else:
            self.ext_btn.configure(bg="#FFFFFF", fg=c["primary"],
                                   font=("微软雅黑", 9, "bold"))
            self.purpose_btn.configure(bg=c["primary"], fg="#FFFFFF",
                                       font=("微软雅黑", 9))
        if self.selected_folder.get():
            self._init_organizer()
        mode_name = "用途分类" if mode == "purpose" else "扩展名分类"
        self.status_var.set(f"🔄 分类模式切换为: {mode_name}")

    def _update_theme_toggle_btn(self):
        self.theme_toggle_btn.configure(
            text="☀️" if self.theme.is_dark() else "🌙"
        )

    def _toggle_theme(self):
        self.theme.toggle()
        self._apply_theme()
        self._update_theme_toggle_btn()
        self.theme_label.configure(
            text="☀️ 亮色" if self.theme.is_dark() else "🌙 暗色"
        )
        self._redraw_chart()

    # ── Notebook ─────────────────────────────────────────────────

    def _create_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.tab_organize = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_organize, text="  📂 整理  ")
        self._build_organize_tab()

        self.tab_duplicate = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_duplicate, text="  🔁 查重  ")
        self._build_duplicate_tab()

        self.tab_analyze = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_analyze, text="  📊 分析  ")
        self._build_analyze_tab()

        self.tab_rules = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_rules, text="  ⚙️ 规则  ")
        self._build_rules_tab()

        self.tab_logs = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_logs, text="  📝 日志  ")
        self._build_logs_tab()

    # ── 状态栏 ──────────────────────────────────────────────────

    def _create_status_bar(self):
        c = self.theme.colors
        sep = ttk.Separator(self.root, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

        status_frame = tk.Frame(self.root, bg=c["status_bg"], height=28)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self.status_var = tk.StringVar(value="✅ 就绪 — Ctrl+O 选择文件夹  |  Ctrl+P 预览  |  Ctrl+Enter 执行  |  F5 刷新")
        tk.Label(status_frame, textvariable=self.status_var,
                font=("微软雅黑", 8), bg=c["status_bg"], fg=c["status_fg"],
                anchor=tk.W).pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # 右侧：主题指示 + 快捷键提示
        self.theme_label = tk.Label(status_frame,
                                    text="🌙 暗色" if self.theme.is_dark() else "☀️ 亮色",
                                    font=("微软雅黑", 8),
                                    bg=c["status_bg"], fg=c["subtitle"])
        self.theme_label.pack(side=tk.RIGHT, padx=(0, 10))

        shortcut_label = tk.Label(status_frame, text="Ctrl+T 切换主题",
                                 font=("微软雅黑", 8),
                                 bg=c["status_bg"], fg=c["subtitle"])
        shortcut_label.pack(side=tk.RIGHT, padx=(0, 16))

    # ═══════════════════════════════════════════════════════════
    # Tab 1: 整理 — Treeview + 批量选择
    # ═══════════════════════════════════════════════════════════

    def _build_organize_tab(self):
        c = self.theme.colors
        main_pane = ttk.PanedWindow(self.tab_organize, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # —— 左侧面板 ——
        left_panel = tk.Frame(main_pane, bg=c["bg"])
        main_pane.add(left_panel, weight=1)

        # 整理选项卡片
        opts_card = tk.LabelFrame(left_panel, text="⚙️ 整理选项",
                                 bg=c["card_bg"], fg=c["card_fg"],
                                 font=("微软雅黑", 11, "bold"),
                                 padx=12, pady=10, relief=tk.GROOVE, bd=1)
        opts_card.pack(fill=tk.X, pady=(0, 8))

        self.dry_run_var = tk.BooleanVar(value=True)
        cb1 = tk.Checkbutton(opts_card, text="👁️ 预览模式（先看效果，不实际移动）",
                            variable=self.dry_run_var,
                            bg=c["card_bg"], fg=c["card_fg"],
                            font=("微软雅黑", 9),
                            selectcolor=c["card_bg"],
                            activebackground=c["card_bg"])
        cb1.pack(anchor=tk.W, pady=(0, 6))

        # 高级选项
        adv_frame = tk.LabelFrame(opts_card, text="高级选项",
                                  bg=c["card_bg"], fg=c["card_fg"],
                                  font=("微软雅黑", 9),
                                  padx=10, pady=6, relief=tk.GROOVE, bd=1)
        adv_frame.pack(fill=tk.X, pady=(4, 0))

        self.date_group_var = tk.BooleanVar(value=False)
        tk.Checkbutton(adv_frame, text="📅 按月份分组", variable=self.date_group_var,
                      bg=c["card_bg"], fg=c["card_fg"], font=("微软雅黑", 9),
                      selectcolor=c["card_bg"],
                      activebackground=c["card_bg"]).pack(anchor=tk.W, pady=1)

        self.date_suffix_var = tk.BooleanVar(value=False)
        tk.Checkbutton(adv_frame, text="🏷️ 添加日期后缀", variable=self.date_suffix_var,
                      bg=c["card_bg"], fg=c["card_fg"], font=("微软雅黑", 9),
                      selectcolor=c["card_bg"],
                      activebackground=c["card_bg"]).pack(anchor=tk.W, pady=1)

        self.num_prefix_var = tk.BooleanVar(value=True)
        tk.Checkbutton(adv_frame, text="🔢 数字前缀排序", variable=self.num_prefix_var,
                      bg=c["card_bg"], fg=c["card_fg"], font=("微软雅黑", 9),
                      selectcolor=c["card_bg"],
                      activebackground=c["card_bg"]).pack(anchor=tk.W, pady=1)

        # 操作按钮组
        actions_card = tk.LabelFrame(left_panel, text="🚀 操作",
                                    bg=c["card_bg"], fg=c["card_fg"],
                                    font=("微软雅黑", 11, "bold"),
                                    padx=12, pady=10, relief=tk.GROOVE, bd=1)
        actions_card.pack(fill=tk.X, pady=(0, 8))

        btn_config = {"font": ("微软雅黑", 9), "relief": tk.FLAT, "cursor": "hand2",
                      "padx": 10, "pady": 4}

        tk.Button(actions_card, text="👁️ 预览整理 (Ctrl+P)",
                 bg=c["primary"], fg="#FFFFFF",
                 activebackground=c["primary"],
                 command=self._preview_organize, **btn_config).pack(fill=tk.X, pady=2)

        tk.Button(actions_card, text="▶️ 执行整理 (Ctrl+Enter)",
                 bg=c["success"], fg="#FFFFFF",
                 activebackground=c["success"],
                 command=self._execute_organize, **btn_config).pack(fill=tk.X, pady=2)

        sep = tk.Frame(actions_card, height=1, bg=c["border"])
        sep.pack(fill=tk.X, pady=6)

        tk.Button(actions_card, text="🧹 一键清理",
                 bg=c["warning"], fg="#FFFFFF",
                 activebackground=c["warning"],
                 command=self._cleanup, **btn_config).pack(fill=tk.X, pady=2)

        tk.Button(actions_card, text="🔬 全面诊断",
                 bg="#607D8B", fg="#FFFFFF",
                 activebackground="#607D8B",
                 command=self._diagnose, **btn_config).pack(fill=tk.X, pady=2)

        # 进度条
        progress_card = tk.LabelFrame(left_panel, text="📊 进度",
                                     bg=c["card_bg"], fg=c["card_fg"],
                                     font=("微软雅黑", 11, "bold"),
                                     padx=12, pady=10, relief=tk.GROOVE, bd=1)
        progress_card.pack(fill=tk.X)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_card, variable=self.progress_var,
                                           mode="indeterminate")
        self.progress_bar.pack(fill=tk.X, ipady=4)

        # —— 右侧面板：Treeview 结果表 ——
        right_panel = tk.Frame(main_pane, bg=c["bg"])
        main_pane.add(right_panel, weight=2)

        result_card = tk.LabelFrame(right_panel, text="📋 整理预览",
                                   bg=c["card_bg"], fg=c["card_fg"],
                                   font=("微软雅黑", 11, "bold"),
                                   padx=10, pady=8, relief=tk.GROOVE, bd=1)
        result_card.pack(fill=tk.BOTH, expand=True)

        # Treeview 工具栏
        tree_toolbar = tk.Frame(result_card, bg=c["card_bg"])
        tree_toolbar.pack(fill=tk.X, pady=(0, 6))

        tk.Button(tree_toolbar, text="☑ 全选", font=("微软雅黑", 8),
                 bg=c["primary"], fg="#FFFFFF", relief=tk.FLAT,
                 padx=8, cursor="hand2",
                 command=self._select_all_org).pack(side=tk.LEFT, padx=2)

        tk.Button(tree_toolbar, text="☐ 全不选", font=("微软雅黑", 8),
                 bg=c["subtitle"], fg="#FFFFFF", relief=tk.FLAT,
                 padx=8, cursor="hand2",
                 command=self._deselect_all_org).pack(side=tk.LEFT, padx=2)

        tk.Button(tree_toolbar, text="🔄 反选", font=("微软雅黑", 8),
                 bg=c["subtitle"], fg="#FFFFFF", relief=tk.FLAT,
                 padx=8, cursor="hand2",
                 command=self._invert_org_selection).pack(side=tk.LEFT, padx=2)

        self.org_summary_var = tk.StringVar(value="选择文件夹后点击预览")
        tk.Label(tree_toolbar, textvariable=self.org_summary_var,
                font=("微软雅黑", 8), bg=c["card_bg"], fg=c["subtitle"]).pack(side=tk.RIGHT, padx=8)

        # Treeview
        columns = ("sel", "filename", "category", "target", "size", "date")
        self.org_tree = ttk.Treeview(result_card, columns=columns, show="headings",
                                     selectmode="extended", height=14)

        self.org_tree.heading("sel", text="✓", anchor=tk.CENTER)
        self.org_tree.heading("filename", text="文件名", anchor=tk.W,
                             command=lambda: self._sort_treeview(self.org_tree, "filename", False))
        self.org_tree.heading("category", text="分类", anchor=tk.W,
                             command=lambda: self._sort_treeview(self.org_tree, "category", False))
        self.org_tree.heading("target", text="目标路径", anchor=tk.W,
                             command=lambda: self._sort_treeview(self.org_tree, "target", False))
        self.org_tree.heading("size", text="大小", anchor=tk.E,
                             command=lambda: self._sort_treeview(self.org_tree, "size", False))
        self.org_tree.heading("date", text="修改日期", anchor=tk.CENTER)

        self.org_tree.column("sel", width=35, anchor=tk.CENTER, stretch=False)
        self.org_tree.column("filename", width=200, anchor=tk.W)
        self.org_tree.column("category", width=90, anchor=tk.W)
        self.org_tree.column("target", width=200, anchor=tk.W)
        self.org_tree.column("size", width=80, anchor=tk.E)
        self.org_tree.column("date", width=100, anchor=tk.CENTER)

        org_scroll = ttk.Scrollbar(result_card, orient=tk.VERTICAL,
                                   command=self.org_tree.yview)
        self.org_tree.configure(yscrollcommand=org_scroll.set)
        self.org_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        org_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 点击切换勾选
        self.org_tree.bind("<ButtonRelease-1>", self._on_org_tree_click)

    def _on_org_tree_click(self, event):
        """点击切换复选框"""
        region = self.org_tree.identify_region(event.x, event.y)
        if region == "cell":
            col = self.org_tree.identify_column(event.x)
            if col == "#1":  # sel column
                item = self.org_tree.identify_row(event.y)
                if item:
                    current = self.org_tree.set(item, "sel")
                    self.org_tree.set(item, "sel", "" if current == "✓" else "✓")

    def _select_all_org(self):
        for item in self.org_tree.get_children():
            self.org_tree.set(item, "sel", "✓")

    def _deselect_all_org(self):
        for item in self.org_tree.get_children():
            self.org_tree.set(item, "sel", "")

    def _invert_org_selection(self):
        for item in self.org_tree.get_children():
            current = self.org_tree.set(item, "sel")
            self.org_tree.set(item, "sel", "" if current == "✓" else "✓")

    @staticmethod
    def _sort_treeview(tree, col, descending):
        """对 Treeview 某列排序"""
        data = [(tree.set(child, col), child) for child in tree.get_children("")]
        try:
            data.sort(key=lambda x: float(x[0].replace(",", "").split()[0])
                     if x[0].replace(",", "").split()[0].replace(".", "").isdigit()
                     else x[0].lower(), reverse=descending)
        except Exception:
            data.sort(key=lambda x: x[0].lower(), reverse=descending)
        for idx, (_, child) in enumerate(data):
            tree.move(child, "", idx)
        tree.heading(col, command=lambda: EnhancedGUI._sort_treeview(tree, col, not descending))

    # ═══════════════════════════════════════════════════════════
    # Tab 2: 查重 — 树形展开 + 全选重复项 + 双击预览
    # ═══════════════════════════════════════════════════════════

    def _build_duplicate_tab(self):
        c = self.theme.colors
        pad = {"padx": 8, "pady": 8}

        top_frame = tk.Frame(self.tab_duplicate, bg=c["bg"])
        top_frame.pack(fill=tk.X, **pad)

        scan_card = tk.LabelFrame(top_frame, text="🔍 扫描操作",
                                 bg=c["card_bg"], fg=c["card_fg"],
                                 font=("微软雅黑", 11, "bold"),
                                 padx=12, pady=10, relief=tk.GROOVE, bd=1)
        scan_card.pack(fill=tk.X, pady=(0, 6))

        scan_inner = tk.Frame(scan_card, bg=c["card_bg"])
        scan_inner.pack(fill=tk.X)

        btn_cfg = {"font": ("微软雅黑", 9), "relief": tk.FLAT, "cursor": "hand2",
                   "padx": 12, "pady": 4}

        tk.Button(scan_inner, text="🔎 扫描重复文件",
                 bg=c["primary"], fg="#FFFFFF", activebackground=c["primary"],
                 command=self._scan_duplicates, **btn_cfg).pack(side=tk.LEFT, padx=2)

        tk.Button(scan_inner, text="☑ 选中所有重复项",
                 bg=c["warning"], fg="#FFFFFF", activebackground=c["warning"],
                 command=self._select_all_dupes, **btn_cfg).pack(side=tk.LEFT, padx=2)

        tk.Button(scan_inner, text="🗑️ 删除选中",
                 bg=c["danger"], fg="#FFFFFF", activebackground=c["danger"],
                 command=self._delete_duplicates, **btn_cfg).pack(side=tk.LEFT, padx=2)

        tk.Label(scan_inner, text="💡 保留每组第一项，选中需要删除的重复项",
                font=("微软雅黑", 9), bg=c["card_bg"], fg=c["subtitle"]).pack(side=tk.LEFT, padx=16)

        # 统计信息
        stats_card = tk.LabelFrame(top_frame, text="📊 统计信息",
                                  bg=c["card_bg"], fg=c["card_fg"],
                                  font=("微软雅黑", 11, "bold"),
                                  padx=12, pady=8, relief=tk.GROOVE, bd=1)
        stats_card.pack(fill=tk.X)

        self.dup_stats_var = tk.StringVar(value="✅ 就绪 - 点击扫描开始检测重复文件")
        tk.Label(stats_card, textvariable=self.dup_stats_var,
                font=("微软雅黑", 10), bg=c["card_bg"],
                fg=c["success"]).pack(anchor=tk.W)

        # Treeview（支持树形展开）
        tree_card = tk.LabelFrame(self.tab_duplicate, text="📁 重复文件列表",
                                 bg=c["card_bg"], fg=c["card_fg"],
                                 font=("微软雅黑", 11, "bold"),
                                 padx=10, pady=8, relief=tk.GROOVE, bd=1)
        tree_card.pack(fill=tk.BOTH, expand=True, **pad)

        columns = ("filename", "size", "md5")
        self.dup_tree = ttk.Treeview(tree_card, columns=columns, show="tree headings",
                                     selectmode="extended", height=16)

        self.dup_tree.heading("#0", text="组/文件", anchor=tk.W)
        self.dup_tree.heading("filename", text="文件名", anchor=tk.W)
        self.dup_tree.heading("size", text="大小", anchor=tk.E)
        self.dup_tree.heading("md5", text="MD5 (前8位)", anchor=tk.CENTER)

        self.dup_tree.column("#0", width=120, stretch=False)
        self.dup_tree.column("filename", width=380, anchor=tk.W)
        self.dup_tree.column("size", width=100, anchor=tk.E)
        self.dup_tree.column("md5", width=110, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tree_card, orient=tk.VERTICAL,
                                  command=self.dup_tree.yview)
        self.dup_tree.configure(yscrollcommand=scrollbar.set)
        self.dup_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击打开文件
        self.dup_tree.bind("<Double-1>", self._on_dup_double_click)

    def _on_dup_double_click(self, event):
        """双击打开文件"""
        item = self.dup_tree.identify_row(event.y)
        if not item:
            return
        filepath = getattr(self, "_dup_file_map", {}).get(item)
        if filepath and filepath.exists():
            try:
                os.startfile(str(filepath))
            except Exception:
                pass

    def _select_all_dupes(self):
        """选中所有重复项（跳过每组的第一个——即保留原始文件）"""
        for group_item in self.dup_tree.get_children():
            children = self.dup_tree.get_children(group_item)
            for child in children[1:]:  # 跳过第一个（保留）
                self.dup_tree.selection_add(child)

    # ═══════════════════════════════════════════════════════════
    # Tab 3: 分析 — Canvas 可视化 + Treeview 统计表
    # ═══════════════════════════════════════════════════════════

    def _build_analyze_tab(self):
        c = self.theme.colors
        pad = {"padx": 8, "pady": 8}

        top_frame = tk.Frame(self.tab_analyze, bg=c["bg"])
        top_frame.pack(fill=tk.X, **pad)

        actions_card = tk.LabelFrame(top_frame, text="📊 分析操作",
                                    bg=c["card_bg"], fg=c["card_fg"],
                                    font=("微软雅黑", 11, "bold"),
                                    padx=12, pady=10, relief=tk.GROOVE, bd=1)
        actions_card.pack(fill=tk.X)

        actions_inner = tk.Frame(actions_card, bg=c["card_bg"])
        actions_inner.pack(fill=tk.X)

        btn_cfg = {"font": ("微软雅黑", 9), "relief": tk.FLAT, "cursor": "hand2",
                   "padx": 12, "pady": 4}

        tk.Button(actions_inner, text="🔬 执行分析 (F5)",
                 bg=c["primary"], fg="#FFFFFF", activebackground=c["primary"],
                 command=self._run_analysis, **btn_cfg).pack(side=tk.LEFT, padx=2)

        tk.Button(actions_inner, text="📄 导出 Markdown",
                 bg=c["success"], fg="#FFFFFF", activebackground=c["success"],
                 command=self._export_markdown, **btn_cfg).pack(side=tk.LEFT, padx=2)

        tk.Button(actions_inner, text="📊 导出 JSON",
                 bg="#607D8B", fg="#FFFFFF", activebackground="#607D8B",
                 command=self._export_json, **btn_cfg).pack(side=tk.LEFT, padx=2)

        # 主区域：分栏 — 左侧图表，右侧统计表
        main_pane = ttk.PanedWindow(self.tab_analyze, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, **pad)

        # 左侧：Canvas 图表
        chart_frame = tk.LabelFrame(main_pane, text="📈 扩展名分布 (Top 10)",
                                   bg=c["card_bg"], fg=c["card_fg"],
                                   font=("微软雅黑", 11, "bold"),
                                   padx=10, pady=8, relief=tk.GROOVE, bd=1)
        main_pane.add(chart_frame, weight=1)

        self.analyze_canvas = tk.Canvas(chart_frame, bg=c["canvas_bg"],
                                        height=280, highlightthickness=0)
        self.analyze_canvas.pack(fill=tk.BOTH, expand=True)
        self._chart_data = None

        # 右侧：统计表
        stats_panel = tk.Frame(main_pane, bg=c["bg"])
        main_pane.add(stats_panel, weight=1)

        table_card = tk.LabelFrame(stats_panel, text="📋 统计详情",
                                  bg=c["card_bg"], fg=c["card_fg"],
                                  font=("微软雅黑", 11, "bold"),
                                  padx=10, pady=8, relief=tk.GROOVE, bd=1)
        table_card.pack(fill=tk.BOTH, expand=True)

        columns = ("metric", "value")
        self.analyze_tree = ttk.Treeview(table_card, columns=columns, show="headings",
                                         height=14)
        self.analyze_tree.heading("metric", text="指标", anchor=tk.W)
        self.analyze_tree.heading("value", text="数值", anchor=tk.W)
        self.analyze_tree.column("metric", width=140, anchor=tk.W)
        self.analyze_tree.column("value", width=200, anchor=tk.W)
        self.analyze_tree.pack(fill=tk.BOTH, expand=True)

    def _draw_bar_chart(self, canvas, data, width, height):
        """在 Canvas 上绘制水平柱状图"""
        c = self.theme.colors
        canvas.delete("all")

        if not data:
            canvas.create_text(width // 2, height // 2, text="暂无数据",
                              fill=c["subtitle"], font=("微软雅黑", 12))
            return

        max_val = max(v for _, v in data)
        if max_val == 0:
            return

        bar_height = min(24, max(16, (height - 60) // len(data)))
        chart_w = width - 160
        start_y = 20

        colors = c["chart_colors"]
        for i, (label, val) in enumerate(data):
            y = start_y + i * (bar_height + 4)
            bar_w = int((val / max_val) * chart_w) if max_val > 0 else 0
            bar_w = max(bar_w, 2)

            color_idx = i % len(colors)

            # 标签
            canvas.create_text(5, y + bar_height // 2, text=label[:12],
                              anchor=tk.W, fill=c["fg"],
                              font=("微软雅黑", 9))

            # 条
            x0 = 80
            canvas.create_rectangle(x0, y, x0 + bar_w, y + bar_height,
                                   fill=colors[color_idx], outline="", tags="bar")

            # 值
            canvas.create_text(x0 + bar_w + 6, y + bar_height // 2,
                              text=str(val), anchor=tk.W, fill=c["fg"],
                              font=("Consolas", 9))

        # 网格线
        for i in range(5):
            y = start_y + i * ((height - 40) // 4)
            canvas.create_line(80, y, width - 10, y, fill=c["canvas_grid"], dash=(2, 4))

    def _redraw_chart(self):
        if self._chart_data:
            w = self.analyze_canvas.winfo_width()
            h = self.analyze_canvas.winfo_height()
            if w > 10 and h > 10:
                self._draw_bar_chart(self.analyze_canvas, self._chart_data, w, h)

    # ═══════════════════════════════════════════════════════════
    # Tab 4: 规则 — JSON 校验 + 导入/导出 + 搜索
    # ═══════════════════════════════════════════════════════════

    def _build_rules_tab(self):
        c = self.theme.colors
        pad = {"padx": 8, "pady": 8}

        sub_notebook = ttk.Notebook(self.tab_rules)
        sub_notebook.pack(fill=tk.BOTH, expand=True, **pad)

        # === 4a: 扩展名规则 ===
        rules_frame = tk.Frame(sub_notebook, bg=c["bg"])
        sub_notebook.add(rules_frame, text="📋 扩展名规则")

        # 工具栏
        rules_toolbar = tk.Frame(rules_frame, bg=c["bg"])
        rules_toolbar.pack(fill=tk.X, padx=6, pady=(6, 0))

        self.rules_search_var = tk.StringVar()
        self.rules_search_var.trace_add("write", lambda *_: self._filter_rules())
        tk.Entry(rules_toolbar, textvariable=self.rules_search_var,
                font=("微软雅黑", 9), width=20).pack(side=tk.LEFT, padx=2)
        tk.Label(rules_toolbar, text="🔍 搜索", font=("微软雅黑", 8),
                bg=c["bg"], fg=c["subtitle"]).pack(side=tk.LEFT)

        btn_cfg = {"font": ("微软雅黑", 9), "relief": tk.FLAT, "cursor": "hand2",
                   "padx": 10, "pady": 3}

        tk.Button(rules_toolbar, text="💾 保存", bg=c["primary"], fg="#FFFFFF",
                 activebackground=c["primary"],
                 command=self._save_rules, **btn_cfg).pack(side=tk.RIGHT, padx=2)

        tk.Button(rules_toolbar, text="📥 导入", bg=c["success"], fg="#FFFFFF",
                 activebackground=c["success"],
                 command=self._import_rules, **btn_cfg).pack(side=tk.RIGHT, padx=2)

        tk.Button(rules_toolbar, text="📤 导出", bg="#607D8B", fg="#FFFFFF",
                 activebackground="#607D8B",
                 command=self._export_rules_file, **btn_cfg).pack(side=tk.RIGHT, padx=2)

        tk.Button(rules_toolbar, text="🔄 重置默认", bg=c["warning"], fg="#FFFFFF",
                 activebackground=c["warning"],
                 command=self._reset_rules, **btn_cfg).pack(side=tk.RIGHT, padx=2)

        # JSON 校验状态
        self.rules_valid_var = tk.StringVar(value="")
        tk.Label(rules_toolbar, textvariable=self.rules_valid_var,
                font=("微软雅黑", 9), bg=c["bg"], fg=c["success"]).pack(side=tk.RIGHT, padx=12)

        # 编辑器
        editor_card = tk.LabelFrame(rules_frame, text="✏️ JSON 规则编辑器",
                                   bg=c["card_bg"], fg=c["card_fg"],
                                   font=("微软雅黑", 11, "bold"),
                                   padx=10, pady=8, relief=tk.GROOVE, bd=1)
        editor_card.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.rules_text = scrolledtext.ScrolledText(editor_card,
                                                     font=("Consolas", 10),
                                                     wrap=tk.WORD,
                                                     bg=c["text_bg"],
                                                     fg=c["text_fg"],
                                                     insertbackground=c["fg"],
                                                     padx=10,
                                                     pady=10)
        self.rules_text.pack(fill=tk.BOTH, expand=True)
        self.rules_text.bind("<<Modified>>", self._on_rules_modified)

        # === 4b: 关键词映射 ===
        kw_frame = tk.Frame(sub_notebook, bg=c["bg"])
        sub_notebook.add(kw_frame, text="🔑 关键词映射")

        kw_toolbar = tk.Frame(kw_frame, bg=c["bg"])
        kw_toolbar.pack(fill=tk.X, padx=6, pady=(6, 0))

        self.kw_search_var = tk.StringVar()
        self.kw_search_var.trace_add("write", lambda *_: self._filter_keywords())
        tk.Entry(kw_toolbar, textvariable=self.kw_search_var,
                font=("微软雅黑", 9), width=20).pack(side=tk.LEFT, padx=2)
        tk.Label(kw_toolbar, text="🔍 过滤", font=("微软雅黑", 8),
                bg=c["bg"], fg=c["subtitle"]).pack(side=tk.LEFT)

        tk.Button(kw_toolbar, text="💾 保存关键词", bg=c["primary"], fg="#FFFFFF",
                 activebackground=c["primary"],
                 command=self._save_keywords, **btn_cfg).pack(side=tk.RIGHT, padx=2)

        tk.Button(kw_toolbar, text="📖 分类详情", bg=c["success"], fg="#FFFFFF",
                 activebackground=c["success"],
                 command=self._show_categories, **btn_cfg).pack(side=tk.RIGHT, padx=2)

        kw_editor_card = tk.LabelFrame(kw_frame, text="✏️ 关键词编辑器 (关键词=分类名)",
                                      bg=c["card_bg"], fg=c["card_fg"],
                                      font=("微软雅黑", 11, "bold"),
                                      padx=10, pady=8, relief=tk.GROOVE, bd=1)
        kw_editor_card.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.kw_text = scrolledtext.ScrolledText(kw_editor_card,
                                                  font=("Consolas", 10),
                                                  wrap=tk.WORD,
                                                  bg=c["text_bg"],
                                                  fg=c["text_fg"],
                                                  insertbackground=c["fg"],
                                                  padx=10,
                                                  pady=10)
        self.kw_text.pack(fill=tk.BOTH, expand=True)

    def _on_rules_modified(self, event=None):
        """实时校验 JSON 格式"""
        text = self.rules_text.get(1.0, tk.END)
        try:
            json.loads(text)
            self.rules_valid_var.set("✅ JSON 格式正确")
            self.rules_text.tag_remove("error", "1.0", tk.END)
        except json.JSONDecodeError as e:
            self.rules_valid_var.set(f"❌ 格式错误: {e}")
            # 高亮错误行
            self.rules_text.tag_remove("error", "1.0", tk.END)
            self.rules_text.tag_configure("error", foreground="red")
        self.rules_text.edit_modified(False)

    def _filter_rules(self):
        """搜索过滤规则编辑器内容 — 滚动到匹配行"""
        query = self.rules_search_var.get().strip()
        if not query:
            self.rules_text.tag_remove("highlight", "1.0", tk.END)
            return
        self.rules_text.tag_remove("highlight", "1.0", tk.END)
        self.rules_text.tag_configure("highlight", background="#FFEB3B", foreground="#333333")
        start = "1.0"
        while True:
            pos = self.rules_text.search(query, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self.rules_text.tag_add("highlight", pos, end)
            start = end

    def _filter_keywords(self):
        """搜索过滤关键词编辑器"""
        query = self.kw_search_var.get().strip()
        if not query:
            self.kw_text.tag_remove("highlight", "1.0", tk.END)
            return
        self.kw_text.tag_remove("highlight", "1.0", tk.END)
        self.kw_text.tag_configure("highlight", background="#FFEB3B", foreground="#333333")
        start = "1.0"
        while True:
            pos = self.kw_text.search(query, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self.kw_text.tag_add("highlight", pos, end)
            start = end

    def _import_rules(self):
        """导入 JSON 规则文件"""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")],
            title="导入分类规则"
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            self.rules_text.delete(1.0, tk.END)
            self.rules_text.insert(tk.END, json.dumps(rules, indent=2, ensure_ascii=False))
            self.status_var.set(f"✅ 已导入规则: {filepath}")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def _export_rules_file(self):
        """导出 JSON 规则文件"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")],
            title="导出分类规则"
        )
        if not filepath:
            return
        try:
            text = self.rules_text.get(1.0, tk.END)
            json.loads(text)  # 校验
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
            self.status_var.set(f"✅ 规则已导出: {filepath}")
            messagebox.showinfo("导出成功", f"规则已保存到:\n{filepath}")
        except json.JSONDecodeError as e:
            messagebox.showerror("格式错误", f"JSON 格式不正确，请先修正:\n{e}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    # ═══════════════════════════════════════════════════════════
    # Tab 5: 日志 — 级别过滤 + 自动刷新 + 搜索
    # ═══════════════════════════════════════════════════════════

    def _build_logs_tab(self):
        c = self.theme.colors
        pad = {"padx": 8, "pady": 8}

        top_frame = tk.Frame(self.tab_logs, bg=c["bg"])
        top_frame.pack(fill=tk.X, **pad)

        actions_card = tk.LabelFrame(top_frame, text="📝 日志操作",
                                    bg=c["card_bg"], fg=c["card_fg"],
                                    font=("微软雅黑", 11, "bold"),
                                    padx=12, pady=10, relief=tk.GROOVE, bd=1)
        actions_card.pack(fill=tk.X)

        actions_inner = tk.Frame(actions_card, bg=c["card_bg"])
        actions_inner.pack(fill=tk.X)

        btn_cfg = {"font": ("微软雅黑", 9), "relief": tk.FLAT, "cursor": "hand2",
                   "padx": 12, "pady": 4}

        tk.Button(actions_inner, text="🔄 刷新 (F5)",
                 bg=c["primary"], fg="#FFFFFF", activebackground=c["primary"],
                 command=self._refresh_logs, **btn_cfg).pack(side=tk.LEFT, padx=2)

        tk.Button(actions_inner, text="🗑️ 清除显示",
                 bg=c["warning"], fg="#FFFFFF", activebackground=c["warning"],
                 command=self._clear_logs, **btn_cfg).pack(side=tk.LEFT, padx=2)

        # 自动刷新开关
        tk.Checkbutton(actions_inner, text="🔄 自动刷新",
                      variable=self.auto_refresh_logs,
                      bg=c["card_bg"], fg=c["card_fg"],
                      font=("微软雅黑", 9),
                      selectcolor=c["card_bg"],
                      activebackground=c["card_bg"],
                      command=self._toggle_auto_refresh).pack(side=tk.LEFT, padx=16)

        # 级别过滤
        tk.Label(actions_inner, text="级别:", font=("微软雅黑", 9),
                bg=c["card_bg"], fg=c["card_fg"]).pack(side=tk.LEFT, padx=(16, 4))

        level_cb = ttk.Combobox(actions_inner, textvariable=self.log_filter_level,
                               values=["ALL", "INFO", "WARNING", "ERROR"],
                               state="readonly", width=10)
        level_cb.pack(side=tk.LEFT)
        level_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_logs())

        # 搜索
        self.log_search_var = tk.StringVar()
        tk.Entry(actions_inner, textvariable=self.log_search_var,
                font=("微软雅黑", 9), width=16).pack(side=tk.RIGHT, padx=4)
        tk.Label(actions_inner, text="🔍 搜索", font=("微软雅黑", 8),
                bg=c["card_bg"], fg=c["subtitle"]).pack(side=tk.RIGHT)

        tk.Button(actions_inner, text="查找", font=("微软雅黑", 9),
                 relief=tk.FLAT, padx=8, pady=2,
                 bg=c["subtitle"], fg="#FFFFFF",
                 command=self._search_logs).pack(side=tk.RIGHT, padx=2)

        # 日志显示
        log_card = tk.LabelFrame(self.tab_logs, text="📜 操作历史",
                                bg=c["card_bg"], fg=c["card_fg"],
                                font=("微软雅黑", 11, "bold"),
                                padx=10, pady=8, relief=tk.GROOVE, bd=1)
        log_card.pack(fill=tk.BOTH, expand=True, **pad)

        self.logs_text = scrolledtext.ScrolledText(log_card,
                                                    font=("Consolas", 10),
                                                    wrap=tk.WORD,
                                                    bg=c["text_bg"],
                                                    fg=c["text_fg"],
                                                    insertbackground=c["fg"],
                                                    padx=10,
                                                    pady=10)
        self.logs_text.pack(fill=tk.BOTH, expand=True)

    def _toggle_auto_refresh(self):
        if self.auto_refresh_logs.get():
            self._schedule_auto_refresh()
            self.status_var.set("🔄 日志自动刷新已开启")
        else:
            self.status_var.set("📝 日志自动刷新已关闭")

    def _schedule_auto_refresh(self):
        if self.auto_refresh_logs.get():
            self._refresh_logs()
            self.root.after(5000, self._schedule_auto_refresh)

    def _search_logs(self):
        query = self.log_search_var.get().strip()
        if not query:
            return
        self.logs_text.tag_remove("highlight", "1.0", tk.END)
        self.logs_text.tag_configure("highlight", background="#FFEB3B", foreground="#333333")
        start = "1.0"
        count = 0
        while True:
            pos = self.logs_text.search(query, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self.logs_text.tag_add("highlight", pos, end)
            start = end
            count += 1
        self.status_var.set(f"🔍 找到 {count} 处匹配" if count else f"🔍 未找到: {query}")

    # ═══════════════════════════════════════════════════════════
    # 事件处理（保持向后兼容）
    # ═══════════════════════════════════════════════════════════

    def _select_folder(self):
        folder = filedialog.askdirectory(title="选择目标文件夹")
        if folder:
            self.selected_folder.set(folder)
            self._init_organizer()
            self.status_var.set(f"✅ 已选择: {folder}")

    def _on_mode_change(self, *_):
        if self.selected_folder.get():
            self._init_organizer()
        mode_name = "用途分类" if self.mode.get() == "purpose" else "扩展名分类"
        self.status_var.set(f"🔄 分类模式切换为: {mode_name}")

    def _init_organizer(self):
        folder = self.selected_folder.get()
        if not folder:
            return
        from organizer import FileOrganizer
        self.organizer = FileOrganizer(download_folder=folder, mode=self.mode.get())

    def _ensure_organizer(self):
        if not self.selected_folder.get():
            messagebox.showwarning("⚠️ 提示", "请先选择目标文件夹")
            return False
        if self.organizer is None:
            self._init_organizer()
            if self.organizer is None:
                return False
        return True

    def _load_last_folder(self):
        try:
            config_file = Path.home() / ".download_organizer_config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    last_folder = config.get('last_folder', '')
                    if last_folder and Path(last_folder).exists():
                        self.selected_folder.set(last_folder)
                        self._init_organizer()
        except Exception:
            pass

    def _save_last_folder(self):
        try:
            config_file = Path.home() / ".download_organizer_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({'last_folder': self.selected_folder.get()}, f,
                         ensure_ascii=False, indent=2)
        except Exception:
            pass

    def on_close(self):
        self._save_last_folder()
        self.root.destroy()

    # ═══════════════════════════════════════════════════════════
    # Tab 1: 整理方法
    # ═══════════════════════════════════════════════════════════

    def _preview_organize(self):
        if not self._ensure_organizer():
            return

        self.org_tree.delete(*self.org_tree.get_children())
        self.org_summary_var.set("⏳ 正在分析...")
        self.root.update()

        try:
            date_group = self.date_group_var.get()
            date_suffix = self.date_suffix_var.get()
            num_prefix = self.num_prefix_var.get()

            moved_files, duplicates = self.organizer.organize(
                dry_run=True,
                use_date_grouping=date_group,
                add_date_suffix=date_suffix,
                use_number_prefix=num_prefix,
            )

            # 填充 Treeview
            for old_name, new_path in moved_files:
                # 获取文件信息
                full_old_path = Path(self.selected_folder.get()) / old_name
                try:
                    size = full_old_path.stat().st_size
                    size_str = self._format_size(size)
                    mtime = datetime.fromtimestamp(full_old_path.stat().st_mtime)
                    date_str = mtime.strftime("%Y-%m-%d %H:%M")
                except OSError:
                    size_str = "?"
                    date_str = "?"

                # 提取分类
                category = Path(new_path).parent.name

                self.org_tree.insert("", tk.END, values=(
                    "✓", old_name, category, new_path, size_str, date_str
                ))

            self.org_summary_var.set(
                f"共 {len(moved_files)} 个文件将整理{f'，{len(duplicates)} 组重复' if duplicates else ''}"
            )
            self.status_var.set(f"✅ 预览完成 — 将整理 {len(moved_files)} 个文件")
        except Exception as e:
            messagebox.showerror("错误", f"预览失败: {str(e)}")
            self.status_var.set("❌ 预览失败")

    def _execute_organize(self):
        if not self._ensure_organizer():
            return

        if self.dry_run_var.get():
            if not messagebox.askyesno("确认", "当前为预览模式，是否切换到执行模式？"):
                return
            self.dry_run_var.set(False)

        confirm = messagebox.askyesno(
            "⚠️ 确认执行",
            "即将开始整理文件，此操作不可撤销！\n\n是否继续？"
        )
        if not confirm:
            return

        self._run_in_thread(self._do_execute_organize)

    def _do_execute_organize(self):
        try:
            date_group = self.date_group_var.get()
            date_suffix = self.date_suffix_var.get()
            num_prefix = self.num_prefix_var.get()

            moved_files, duplicates = self.organizer.organize(
                dry_run=False,
                use_date_grouping=date_group,
                add_date_suffix=date_suffix,
                use_number_prefix=num_prefix,
            )

            def update_ui():
                self.progress_bar.stop()
                self.status_var.set("✅ 整理完成")
                messagebox.showinfo("成功", f"文件整理完成！共移动 {len(moved_files)} 个文件。")

            self.root.after(0, update_ui)
        except Exception as e:
            def show_error():
                self.progress_bar.stop()
                messagebox.showerror("错误", f"整理失败: {str(e)}")
                self.status_var.set("❌ 整理失败")

            self.root.after(0, show_error)

    def _cleanup(self):
        if not self._ensure_organizer():
            return

        confirm = messagebox.askyesno(
            "🧹 确认清理",
            "将执行以下操作：\n"
            "- 删除临时文件 (.tmp, ~$等)\n"
            "- 清理空文件夹\n\n"
            "是否继续？"
        )
        if not confirm:
            return

        self._run_in_thread(self._do_cleanup)

    def _do_cleanup(self):
        try:
            is_dry_run = self.dry_run_var.get()
            result = self.organizer.cleanup(dry_run=is_dry_run)

            def update_ui():
                self.progress_bar.stop()
                msg = (f"🧹 清理完成: {len(result['temp_files'])} 临时文件, "
                       f"{len(result['empty_dirs'])} 空目录"
                       f"{' (预览)' if is_dry_run else ' (已删除)'}")
                self.status_var.set(msg)
                if is_dry_run:
                    messagebox.showinfo("预览", msg + "\n\n取消「预览模式」后再次执行以实际清理。")

            self.root.after(0, update_ui)
        except Exception as e:
            def show_error():
                self.progress_bar.stop()
                messagebox.showerror("错误", f"清理失败: {str(e)}")

            self.root.after(0, show_error)

    def _diagnose(self):
        if not self._ensure_organizer():
            return
        try:
            result = self.organizer.diagnose()

            naming = result.get("naming_issues", {})
            storage = result.get("storage_analysis", {})
            dups = result.get("duplicates", [])
            archive = result.get("archive_plan", {})

            total_mb = storage.get("total_size_bytes", 0) / (1024 * 1024)
            stale_mb = storage.get("stale_size_bytes", 0) / (1024 * 1024)

            info = (
                f"🔬 全面诊断报告\n{'=' * 50}\n"
                f"📛 命名: 缺日期后缀 {len(naming.get('needs_date_suffix', []))}个 | "
                f"缺前缀 {len(naming.get('needs_prefix', []))}个 | "
                f"嵌套过深 {len(naming.get('too_deep_nested', []))}个\n"
                f"💾 存储: 总 {total_mb:.1f}MB | "
                f"过期 {storage.get('stale_count', 0)}个({stale_mb:.1f}MB) | "
                f"大文件 {storage.get('large_count', 0)}个 | "
                f"临时 {storage.get('temp_count', 0)}个 | "
                f"空目录 {storage.get('empty_dir_count', 0)}个\n"
                f"🔁 重复: {len(dups)}组\n"
                f"📦 归档建议: "
                f"{len(archive.get('stale_files', []))}个过期 | "
                f"{len(archive.get('temp_files', []))}个临时 | "
                f"预计释放 {archive.get('estimated_savings_mb', 0):.1f}MB\n"
                f"{'=' * 50}"
            )
            messagebox.showinfo("🔬 诊断报告", info)
            self.status_var.set("✅ 诊断完成")
        except Exception as e:
            messagebox.showerror("错误", f"诊断失败: {str(e)}")

    # ═══════════════════════════════════════════════════════════
    # Tab 2: 查重方法
    # ═══════════════════════════════════════════════════════════

    def _scan_duplicates(self):
        if not self._ensure_organizer():
            return
        self.dup_stats_var.set("⏳ 正在扫描...")
        self._run_in_thread(self._do_scan_duplicates)

    def _do_scan_duplicates(self):
        try:
            duplicates = self.organizer.find_duplicates()

            def update_ui():
                c = self.theme.colors
                for item in self.dup_tree.get_children():
                    self.dup_tree.delete(item)

                self._dup_file_map = {}
                group_count = 0
                total_files = 0

                for group_idx, dup_group in enumerate(duplicates, 1):
                    files = dup_group.get("files", [])
                    md5 = dup_group.get("md5", "")
                    size_bytes = dup_group.get("size", 0)

                    if len(files) < 2:
                        continue

                    group_count += 1
                    size_str = self._format_size(size_bytes)
                    wasted = self._format_size(size_bytes * (len(files) - 1))

                    # 父节点（组）
                    parent_id = self.dup_tree.insert("", tk.END, text=f"📁 第{group_count}组",
                                                    values=(f"{len(files)} 个文件",
                                                            size_str, md5[:8] if md5 else ""),
                                                    open=True, tags=("group",))

                    # 子节点（文件）
                    for i, fp in enumerate(files):
                        try:
                            fsize = fp.stat().st_size
                            fsize_str = self._format_size(fsize)
                        except OSError:
                            fsize_str = "?"

                        tag = "keep" if i == 0 else "dupe"
                        prefix = "⭐ " if i == 0 else "   "
                        child_id = self.dup_tree.insert(parent_id, tk.END,
                                                        text=f"{prefix}{fp.name}",
                                                        values=(fp.name, fsize_str, ""),
                                                        tags=(tag,))
                        self._dup_file_map[child_id] = fp
                        total_files += 1

                    if len(files) > 1:
                        waste_info = f" | 可释放 {wasted}"
                        self.dup_tree.item(parent_id,
                                          text=f"📁 第{group_count}组 ({len(files)}个{waste_info})")

                # 标签颜色
                self.dup_tree.tag_configure("group", font=("微软雅黑", 10, "bold"),
                                           background=c["tree_head_bg"])
                self.dup_tree.tag_configure("keep", foreground=c["success"])
                self.dup_tree.tag_configure("dupe", foreground=c["danger"])

                self.dup_stats_var.set(
                    f"✅ 扫描完成 | {group_count} 组重复，{total_files} 个文件"
                )
                self.status_var.set(f"✅ 找到 {group_count} 组重复文件")

            self.root.after(0, update_ui)
        except Exception as e:
            def show_error():
                self.dup_stats_var.set(f"❌ 扫描失败: {str(e)}")

            self.root.after(0, show_error)

    def _delete_duplicates(self):
        selected = self.dup_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的重复文件（⭐ 标记的为保留项）")
            return

        confirm = messagebox.askyesno(
            "⚠️ 确认删除",
            f"将删除 {len(selected)} 个选中的文件，此操作不可撤销！\n\n"
            "⭐ 标记的文件为建议保留项，不会被删除。\n\n是否继续？"
        )
        if not confirm:
            return

        deleted = 0
        errors = []
        for item in selected:
            fp = self._dup_file_map.get(item)
            if not fp:
                continue
            try:
                fp.unlink()
                deleted += 1
            except OSError as e:
                errors.append(f"{fp.name}: {e}")

        msg = f"已删除 {deleted} 个文件"
        if errors:
            msg += f"\n{len(errors)} 个失败"
        messagebox.showinfo("完成", msg)
        self.status_var.set(f"✅ {msg}")

        if deleted > 0:
            self._scan_duplicates()

    # ═══════════════════════════════════════════════════════════
    # Tab 3: 分析方法
    # ═══════════════════════════════════════════════════════════

    def _run_analysis(self):
        if not self._ensure_organizer():
            return
        self._run_in_thread(self._do_analysis)

    def _do_analysis(self):
        try:
            analysis = self.organizer.analyze()

            def update_ui():
                c = self.theme.colors
                # 填充统计表
                for item in self.analyze_tree.get_children():
                    self.analyze_tree.delete(item)

                total_mb = analysis.get("total_size_bytes", 0) / (1024 * 1024)
                stale_mb = analysis.get("stale_size_bytes", 0) / (1024 * 1024)

                rows = [
                    ("文件总数", f"{analysis.get('total_files', 0):,}"),
                    ("文件夹总数", f"{analysis.get('total_dirs', 0):,}"),
                    ("总占用空间", f"{total_mb:.1f} MB"),
                    ("过期文件", f"{analysis.get('stale_count', 0)} 个 ({stale_mb:.1f} MB)"),
                    ("大文件 (>100MB)", f"{analysis.get('large_count', 0)} 个"),
                    ("临时文件", f"{analysis.get('temp_count', 0)} 个"),
                    ("空目录", f"{analysis.get('empty_dir_count', 0)} 个"),
                    ("重复文件组", f"{len(analysis.get('duplicates', []))} 组"),
                ]
                for metric, value in rows:
                    self.analyze_tree.insert("", tk.END, values=(metric, value))

                # 绘制图表
                by_ext = analysis.get("by_extension", {})
                sorted_exts = sorted(by_ext.items(),
                                    key=lambda x: x[1][0], reverse=True)[:10]
                chart_data = [(ext or "(无)", count) for ext, (count, _) in sorted_exts]
                self._chart_data = chart_data

                w = self.analyze_canvas.winfo_width()
                h = self.analyze_canvas.winfo_height()
                if w > 10 and h > 10:
                    self._draw_bar_chart(self.analyze_canvas, chart_data, w, h)

                self.analyze_canvas.bind("<Configure>", lambda e: self._redraw_chart())

                self.status_var.set("✅ 分析完成")

            self.root.after(0, update_ui)
        except Exception as e:
            def show_error():
                messagebox.showerror("错误", f"分析失败: {str(e)}")

            self.root.after(0, show_error)

    def _export_markdown(self):
        if not self._ensure_organizer():
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("All Files", "*.*")],
            title="导出 Markdown 报告",
        )
        if not filepath:
            return
        self._run_in_thread(self._do_export_md, filepath)

    def _do_export_md(self, filepath):
        try:
            analysis = self.organizer.analyze()
            from reporter import Reporter
            Reporter().to_markdown(analysis, Path(filepath))

            def update_ui():
                self.status_var.set(f"✅ 报告已导出: {filepath}")
                messagebox.showinfo("导出成功", f"报告已保存到:\n{filepath}")

            self.root.after(0, update_ui)
        except Exception as e:
            def show_error():
                messagebox.showerror("错误", f"导出失败: {str(e)}")

            self.root.after(0, show_error)

    def _export_json(self):
        if not self._ensure_organizer():
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")],
            title="导出 JSON 报告",
        )
        if not filepath:
            return
        self._run_in_thread(self._do_export_json, filepath)

    def _do_export_json(self, filepath):
        try:
            analysis = self.organizer.analyze()
            from reporter import Reporter
            Reporter().to_json(analysis, Path(filepath))

            def update_ui():
                self.status_var.set(f"✅ 报告已导出: {filepath}")
                messagebox.showinfo("导出成功", f"报告已保存到:\n{filepath}")

            self.root.after(0, update_ui)
        except Exception as e:
            def show_error():
                messagebox.showerror("错误", f"导出失败: {str(e)}")

            self.root.after(0, show_error)

    # ═══════════════════════════════════════════════════════════
    # Tab 4: 规则方法
    # ═══════════════════════════════════════════════════════════

    def _save_rules(self):
        text = self.rules_text.get(1.0, tk.END)
        try:
            new_rules = json.loads(text)
            if self.organizer and hasattr(self.organizer.classifier, 'update_from_dict'):
                self.organizer.classifier.update_from_dict(new_rules)
                messagebox.showinfo("✅ 成功", "扩展名分类规则已保存")
                self.status_var.set("✅ 规则已更新")
            else:
                messagebox.showinfo("ℹ️ 提示",
                                   "当前为用途分类模式。\n切换到「扩展名分类」模式即可生效。")
                self.status_var.set("✅ 规则已保存（未应用）")
        except json.JSONDecodeError as e:
            messagebox.showerror("❌ JSON 格式错误", str(e))

    def _reset_rules(self):
        from config import DEFAULT_EXTENSION_CATEGORIES
        self.rules_text.delete(1.0, tk.END)
        self.rules_text.insert(tk.END, json.dumps(DEFAULT_EXTENSION_CATEGORIES,
                                                   indent=2, ensure_ascii=False))
        self.status_var.set("🔄 规则已重置为默认")

    def _save_keywords(self):
        text = self.kw_text.get(1.0, tk.END)
        try:
            kw_map = {}
            for line in text.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    kw_map[key.strip()] = val.strip()

            if self.organizer and hasattr(self.organizer.classifier, 'add_keyword'):
                for kw, cat in kw_map.items():
                    self.organizer.classifier.add_keyword(kw, cat)
                messagebox.showinfo("✅ 成功", f"已保存 {len(kw_map)} 条关键词映射")
                self.status_var.set(f"✅ 关键词已更新: {len(kw_map)} 条")
            else:
                messagebox.showinfo("ℹ️ 提示",
                                   "当前为扩展名分类模式。\n切换到「用途分类」模式即可生效。")
                self.status_var.set(f"✅ 已保存 {len(kw_map)} 条关键词（未应用）")
        except Exception as e:
            messagebox.showerror("❌ 错误", str(e))

    def _show_categories(self):
        try:
            if self.organizer and hasattr(self.organizer.classifier, 'get_all_categories'):
                cats = self.organizer.classifier.get_all_categories()
                if hasattr(self.organizer.classifier, 'get_category_info'):
                    info_lines = []
                    for cat in cats:
                        cat_info = self.organizer.classifier.get_category_info(cat)
                        if cat_info:
                            info_lines.append(f"{cat} - {cat_info.get('description', '')}")
                        else:
                            info_lines.append(cat)
                    info = "\n".join(info_lines)
                else:
                    info = "\n".join(cats)
                messagebox.showinfo("📚 分类体系", info)
            else:
                from classifiers import PurposeClassifier
                cats = PurposeClassifier.list_categories_with_info()
                info = "\n".join([f"{c} - {d}" for c, d in cats])
                messagebox.showinfo("📚 8大用途分类体系", info)
        except Exception as e:
            messagebox.showerror("错误", f"获取分类信息失败: {str(e)}")

    # ═══════════════════════════════════════════════════════════
    # Tab 5: 日志方法
    # ═══════════════════════════════════════════════════════════

    def _refresh_logs(self):
        if not self.organizer:
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(tk.END, "请先选择目标文件夹\n")
            return

        try:
            log_dir = self.organizer.log_dir
            log_files = sorted(log_dir.glob("*.log"), reverse=True)[:10]

            self.logs_text.delete(1.0, tk.END)

            if not log_files:
                self.logs_text.insert(tk.END, "暂无操作日志\n")
                self.status_var.set("✅ 日志已刷新（无日志文件）")
                return

            level_filter = self.log_filter_level.get()

            for log_file in log_files:
                self.logs_text.insert(tk.END, f"📄 {log_file.name}\n")
                self.logs_text.insert(tk.END, "-" * 40 + "\n")
                try:
                    content = log_file.read_text(encoding='utf-8', errors='ignore')
                    if level_filter and level_filter != "ALL":
                        filtered_lines = []
                        for line in content.split('\n'):
                            if level_filter in line.upper():
                                filtered_lines.append(line)
                        content = "\n".join(filtered_lines)
                    self.logs_text.insert(tk.END, content + "\n\n")
                except OSError:
                    self.logs_text.insert(tk.END, "(读取失败)\n\n")

            self.status_var.set(f"✅ 日志已刷新（显示 {len(log_files)} 个日志文件）")
        except Exception as e:
            messagebox.showerror("错误", f"刷新日志失败: {str(e)}")

    def _clear_logs(self):
        confirm = messagebox.askyesno("确认", "确定要清除当前显示的日志吗？\n（不会删除硬盘上的日志文件）")
        if confirm:
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(tk.END, "日志显示已清除\n")
            self.status_var.set("🗑️ 日志显示已清除")

    # ═══════════════════════════════════════════════════════════
    # 通用辅助方法
    # ═══════════════════════════════════════════════════════════

    def _run_in_thread(self, func, *args):
        self.progress_bar.start()
        self.is_running = True

        def worker():
            try:
                func(*args)
            except Exception as e:
                def show_error():
                    self.progress_bar.stop()
                    self.is_running = False
                    messagebox.showerror("线程错误", f"任务执行失败: {str(e)}")
                    self.status_var.set("❌ 任务失败")
                self.root.after(0, show_error)
            finally:
                self.is_running = False

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    @staticmethod
    def _format_size(size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = EnhancedGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
