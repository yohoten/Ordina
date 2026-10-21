"""
Tab · 规则
==========
三个子页：
    1. 扩展名规则 —— JSON 实时校验 + 搜索高亮 + 导入/导出/重置
    2. 关键词映射 —— 「关键词=分类」行编辑器
    3. 命名规则   —— NamingRules 的 JSON 编辑与即时应用（新增）
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from ..theme import FONTS, themed_scrolled_text
from ..widgets import button, card, label, status_label
from .base import BaseTab

from ...core import DEFAULT_EXTENSION_CATEGORIES, NamingRules, TEMPLATE_PRESETS


class RulesTab(BaseTab):
    title = "规则"
    icon = "⚙️"

    def build(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_extension_page(notebook)
        self._build_keyword_page(notebook)
        self._build_naming_page(notebook)

    # ═══════════════════════════════════════════════════════════
    # 1. 扩展名规则
    # ═══════════════════════════════════════════════════════════

    def _build_extension_page(self, notebook: ttk.Notebook) -> None:
        page = tk.Frame(notebook)
        self.theme.track(page, bg="bg")
        notebook.add(page, text="  扩展名规则  ")

        body = card(page, self.theme, "扩展名 → 分类")
        body.master.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        toolbar = tk.Frame(body)
        self.theme.track(toolbar, bg="surface")
        toolbar.pack(fill=tk.X, pady=(0, 8))

        self.ext_search_var = tk.StringVar()
        self.ext_search_var.trace_add("write", lambda *_: self._highlight(self.ext_text,
                                                                          self.ext_search_var.get()))
        search = ttk.Entry(toolbar, textvariable=self.ext_search_var, width=18)
        search.pack(side=tk.LEFT)
        label(toolbar, self.theme, "搜索", "small", "fg_subtle").pack(side=tk.LEFT, padx=(4, 12))

        self.ext_state_var = tk.StringVar(value="")
        status_label(toolbar, self.theme, self.ext_state_var, "success").pack(side=tk.LEFT)

        for text, command, variant in (
            ("应用", self._save_extensions, "accent"),
            ("导入", self._import_extensions, "success"),
            ("导出", self._export_extensions, "default"),
            ("重置默认", self._reset_extensions, "warning"),
        ):
            button(toolbar, self.theme, text, command, variant).pack(side=tk.RIGHT, padx=(4, 0))

        self.ext_text = themed_scrolled_text(body, self.theme)
        self.ext_text.pack(fill=tk.BOTH, expand=True)
        self.ext_text.insert(tk.END, json.dumps(DEFAULT_EXTENSION_CATEGORIES,
                                                indent=2, ensure_ascii=False))
        self.ext_text.bind("<<Modified>>", lambda _e: self._validate(self.ext_text,
                                                                     self.ext_state_var))

    # ═══════════════════════════════════════════════════════════
    # 2. 关键词映射
    # ═══════════════════════════════════════════════════════════

    def _build_keyword_page(self, notebook: ttk.Notebook) -> None:
        page = tk.Frame(notebook)
        self.theme.track(page, bg="bg")
        notebook.add(page, text="  关键词映射  ")

        body = card(page, self.theme, "关键词 = 分类名（每行一条，# 开头为注释）")
        body.master.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        toolbar = tk.Frame(body)
        self.theme.track(toolbar, bg="surface")
        toolbar.pack(fill=tk.X, pady=(0, 8))

        self.kw_search_var = tk.StringVar()
        self.kw_search_var.trace_add("write", lambda *_: self._highlight(self.kw_text,
                                                                         self.kw_search_var.get()))
        ttk.Entry(toolbar, textvariable=self.kw_search_var, width=18).pack(side=tk.LEFT)
        label(toolbar, self.theme, "过滤", "small", "fg_subtle").pack(side=tk.LEFT, padx=(4, 12))

        self.kw_state_var = tk.StringVar(value="")
        status_label(toolbar, self.theme, self.kw_state_var).pack(side=tk.LEFT)

        button(toolbar, self.theme, "保存到分类器", self._save_keywords, "accent").pack(side=tk.RIGHT, padx=(4, 0))
        button(toolbar, self.theme, "载入当前词典", self._load_keywords, "default").pack(side=tk.RIGHT, padx=(4, 0))
        button(toolbar, self.theme, "分类体系", self._show_categories, "default").pack(side=tk.RIGHT, padx=(4, 0))

        self.kw_text = themed_scrolled_text(body, self.theme)
        self.kw_text.pack(fill=tk.BOTH, expand=True)
        self._load_keywords()

    # ═══════════════════════════════════════════════════════════
    # 3. 命名规则
    # ═══════════════════════════════════════════════════════════

    def _build_naming_page(self, notebook: ttk.Notebook) -> None:
        page = tk.Frame(notebook)
        self.theme.track(page, bg="bg")
        notebook.add(page, text="  命名规则  ")

        body = card(page, self.theme, "NamingRules（JSON，保存后立即对整个应用生效）")
        body.master.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        toolbar = tk.Frame(body)
        self.theme.track(toolbar, bg="surface")
        toolbar.pack(fill=tk.X, pady=(0, 8))

        self.naming_state_var = tk.StringVar(value="")
        status_label(toolbar, self.theme, self.naming_state_var, "success").pack(side=tk.LEFT)

        for text, command, variant in (
            ("应用", self._apply_naming, "accent"),
            ("导出", self._export_naming, "default"),
            ("导入", self._import_naming, "success"),
            ("重置默认", self._reset_naming, "warning"),
        ):
            button(toolbar, self.theme, text, command, variant).pack(side=tk.RIGHT, padx=(4, 0))

        self.naming_text = themed_scrolled_text(body, self.theme)
        self.naming_text.pack(fill=tk.BOTH, expand=True)
        self.naming_text.insert(tk.END, json.dumps(self.app.naming_rules.to_dict(),
                                                   indent=2, ensure_ascii=False))
        self.naming_text.bind("<<Modified>>", lambda _e: self._validate(self.naming_text,
                                                                        self.naming_state_var))

        hint = (
            "字段说明：file_template 支持 {name} {date} {category} {index}；"
            "date_source 可选 auto / filename / exif / modified / created / now；"
            "conflict_pattern 为冲突消解样式（默认 _v{n}）；"
            "prefix_width 为分类目录数字前缀最小宽度。"
        )
        label(body, self.theme, hint, "small", "fg_subtle").pack(anchor=tk.W, pady=(8, 0))

    # ═══════════════════════════════════════════════════════════
    # 通用：校验 / 高亮
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _validate(widget: tk.Text, state_var: tk.StringVar) -> None:
        text = widget.get("1.0", tk.END)
        try:
            json.loads(text)
            state_var.set("✓ JSON 格式正确")
        except json.JSONDecodeError as exc:
            state_var.set(f"✗ 格式错误：{exc}")
        widget.edit_modified(False)

    def _highlight(self, widget: tk.Text, query: str) -> None:
        widget.tag_remove("match", "1.0", tk.END)
        query = query.strip()
        if not query:
            return
        widget.tag_configure("match", background=self.theme.color("warning"),
                             foreground=self.theme.color("on_accent"))
        start = "1.0"
        while True:
            position = widget.search(query, start, stopindex=tk.END, nocase=True)
            if not position:
                break
            end = f"{position}+{len(query)}c"
            widget.tag_add("match", position, end)
            start = end

    # ═══════════════════════════════════════════════════════════
    # 扩展名规则动作
    # ═══════════════════════════════════════════════════════════

    def _save_extensions(self) -> None:
        try:
            rules = json.loads(self.ext_text.get("1.0", tk.END))
        except json.JSONDecodeError as exc:
            self.error("JSON 格式错误", str(exc))
            return

        organizer = self.app.get_organizer()
        if organizer and hasattr(organizer.classifier, "update_from_dict"):
            organizer.classifier.update_from_dict(rules)
            self.set_status("扩展名规则已应用")
            self.info("成功", "扩展名分类规则已应用。")
        else:
            self.set_status("规则已保存（切到扩展名模式后生效）")
            self.info("提示", "当前为用途分类模式或未选择文件夹。\n切换到「扩展名」模式后规则即刻生效。")

    def _import_extensions(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
                                          title="导入扩展名规则")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            self.error("导入失败", str(exc))
            return
        self.ext_text.delete("1.0", tk.END)
        self.ext_text.insert(tk.END, json.dumps(data, indent=2, ensure_ascii=False))
        self.set_status(f"已导入规则：{path}")

    def _export_extensions(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")],
                                            title="导出扩展名规则")
        if not path:
            return
        try:
            json.loads(self.ext_text.get("1.0", tk.END))
        except json.JSONDecodeError as exc:
            self.error("格式错误", f"请先修正 JSON：{exc}")
            return
        Path(path).write_text(self.ext_text.get("1.0", tk.END), encoding="utf-8")
        self.set_status(f"规则已导出：{path}")

    def _reset_extensions(self) -> None:
        self.ext_text.delete("1.0", tk.END)
        self.ext_text.insert(tk.END, json.dumps(DEFAULT_EXTENSION_CATEGORIES,
                                                indent=2, ensure_ascii=False))
        self.set_status("扩展名规则已重置为默认")

    # ═══════════════════════════════════════════════════════════
    # 关键词动作
    # ═══════════════════════════════════════════════════════════

    def _load_keywords(self) -> None:
        from ...core import KEYWORD_DICTIONARY

        lines = ["# 格式：关键词=分类名", "# 保存后会合并进用途分类器"]
        for keyword, category in KEYWORD_DICTIONARY.items():
            lines.append(f"{keyword}={category}")
        self.kw_text.delete("1.0", tk.END)
        self.kw_text.insert(tk.END, "\n".join(lines))

    def _save_keywords(self) -> None:
        mapping = {}
        for raw in self.kw_text.get("1.0", tk.END).splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            keyword, category = line.split("=", 1)
            mapping[keyword.strip()] = category.strip()

        if not mapping:
            self.warn("提示", "未解析到任何「关键词=分类」映射。")
            return

        organizer = self.app.get_organizer()
        if organizer and hasattr(organizer.classifier, "add_keyword"):
            for keyword, category in mapping.items():
                organizer.classifier.add_keyword(keyword, category)
            self.kw_state_var.set(f"✓ 已应用 {len(mapping)} 条")
            self.set_status(f"关键词已更新：{len(mapping)} 条")
        else:
            self.kw_state_var.set(f"✓ 已保存 {len(mapping)} 条（未应用）")
            self.set_status("已保存，切换到用途分类模式后生效")

    def _show_categories(self) -> None:
        from ...core import PURPOSE_CATEGORIES

        lines = [f"{name}\n    {info['description']}"
                 for name, info in PURPOSE_CATEGORIES.items()]
        self.info("8 大用途分类体系", "\n".join(lines))

    # ═══════════════════════════════════════════════════════════
    # 命名规则动作
    # ═══════════════════════════════════════════════════════════

    def _apply_naming(self) -> None:
        try:
            data = json.loads(self.naming_text.get("1.0", tk.END))
        except json.JSONDecodeError as exc:
            self.error("JSON 格式错误", str(exc))
            return

        rules = NamingRules.from_dict(data)
        if rules.file_template not in TEMPLATE_PRESETS and "{" not in rules.file_template:
            self.warn("提示", "命名模板缺少 {name} 等占位符，已回退默认。")
            rules.file_template = "{name}_{date}"

        self.app.naming_rules = rules
        self.app.rebuild_organizer()
        self.naming_state_var.set("✓ 已应用")
        self.set_status(f"命名规则已应用：{rules.summary()}")

    def _export_naming(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")],
                                            title="导出命名规则")
        if not path:
            return
        Path(path).write_text(json.dumps(self.app.naming_rules.to_dict(),
                                         indent=2, ensure_ascii=False), encoding="utf-8")
        self.set_status(f"命名规则已导出：{path}")

    def _import_naming(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")],
                                          title="导入命名规则")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            self.error("导入失败", str(exc))
            return
        self.naming_text.delete("1.0", tk.END)
        self.naming_text.insert(tk.END, json.dumps(data, indent=2, ensure_ascii=False))
        self.set_status(f"已导入命名规则：{path}")

    def _reset_naming(self) -> None:
        rules = NamingRules()
        self.app.naming_rules = rules
        self.app.rebuild_organizer()
        self.naming_text.delete("1.0", tk.END)
        self.naming_text.insert(tk.END, json.dumps(rules.to_dict(), indent=2, ensure_ascii=False))
        self.set_status("命名规则已重置为默认")

    # ── 生命周期 ──────────────────────────────────────────────

    def on_folder_changed(self) -> None:
        self.naming_text.delete("1.0", tk.END)
        self.naming_text.insert(tk.END, json.dumps(self.app.naming_rules.to_dict(),
                                                   indent=2, ensure_ascii=False))
