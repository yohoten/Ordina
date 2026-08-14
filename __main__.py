"""
下载文件夹整理工具 v2.0 — 主入口
===================================
用法:
  python -m download_organizer            # 启动 GUI
  python -m download_organizer gui         # 启动 GUI
  python -m download_organizer cli ...     # CLI 模式
"""

import sys
import os

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        # 转发到 CLI
        from cli import main as cli_main
        sys.argv.pop(1)  # 移除 "cli" 参数
        cli_main()
    else:
        # 启动 GUI
        try:
            from gui import main as gui_main
            gui_main()
        except ImportError as e:
            print(f"[ERR] 无法启动 GUI: {e}")
            print("[HINT] 尝试安装 tkinter 或使用 CLI 模式: python -m download_organizer cli")
            sys.exit(1)


if __name__ == "__main__":
    main()
