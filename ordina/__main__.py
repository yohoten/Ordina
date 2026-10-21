"""
Ordina / 归序 — 命令行入口
===========================

用法:
    python -m ordina                    # 启动 GUI
    python -m ordina gui                # 启动 GUI
    python -m ordina cli <command> ...  # CLI 模式
"""

import sys


def main() -> None:
    argv = sys.argv[1:]

    if argv and argv[0] == "cli":
        from .cli.main import main as cli_main
        sys.argv.pop(1)                      # 移除 "cli"
        cli_main()
        return

    if argv and argv[0] == "gui":
        sys.argv.pop(1)

    try:
        from .ui.app import launch
    except ImportError as exc:
        print(f"[错误] 无法启动图形界面: {exc}")
        print("[提示] 请确认 Python 安装包含 tkinter；或改用命令行模式:")
        print("       python -m ordina cli --help")
        sys.exit(1)

    sys.exit(launch())


if __name__ == "__main__":
    main()
