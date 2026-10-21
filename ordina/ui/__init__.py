"""图形界面包 (Ordina UI)

结构:
    theme.py    调色板 / 控件注册表 / ttk 样式
    widgets.py  卡片、按钮、分段控件、可排序表格等通用控件
    app.py      主窗口（工具栏 + 标签页 + 状态栏）
    tabs/       各功能标签页
"""

from .app import OrdinaApp, launch

__all__ = ["OrdinaApp", "launch"]
