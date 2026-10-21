"""标签页基类"""

from __future__ import annotations

import tkinter as tk
from typing import Optional


class BaseTab(tk.Frame):
    """
    所有功能标签页的基类

    约定：
        - `build()` 构造界面，子类必须实现
        - `refresh()` 响应 F5 / 切换标签
        - `on_folder_changed()` 目标文件夹变化时的钩子
    """

    title: str = ""
    icon: str = ""

    def __init__(self, master: tk.Misc, app):
        super().__init__(master)
        self.app = app
        self.theme = app.theme
        self.theme.track(self, bg="bg")
        self.build()

    # ── 子类实现 ──────────────────────────────────────────────

    def build(self) -> None:  # pragma: no cover - 抽象
        raise NotImplementedError

    def refresh(self) -> None:
        """F5 / 重新聚焦时的刷新动作"""

    def on_folder_changed(self) -> None:
        """目标文件夹变化时清理旧状态"""

    # ── 便捷方法 ──────────────────────────────────────────────

    def set_status(self, message: str) -> None:
        self.app.set_status(message)

    def warn(self, title: str, message: str) -> None:
        self.app.warn(title, message)

    def info(self, title: str, message: str) -> None:
        self.app.info(title, message)

    def error(self, title: str, message: str) -> None:
        self.app.error(title, message)

    def ask_yes(self, title: str, message: str) -> bool:
        return self.app.ask_yes(title, message)

    def run_async(self, func, *args) -> None:
        self.app.run_async(func, *args)

    @property
    def organizer(self):
        return self.app.get_organizer()
