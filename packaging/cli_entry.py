"""
Ordina CLI 打包入口（供 PyInstaller 使用）
=========================================

打包后命令行用法：
    ordina-cli.exe organize --path %USERPROFILE%\\Downloads
    ordina-cli.exe organize --path ... --execute
    ordina-cli.exe naming
    ordina-cli.exe phone devices

为什么需要独立入口：
    ordina/__main__.py 需要靠第一个参数 "cli" 才进入命令行模式，
    打包成 exe 后用户更习惯直接写子命令，故在此固定分流。
"""

import sys

from ordina.cli.main import main


def run() -> int:
    # 让 argparse 的 prog 显示为 ordina-cli，而非入口脚本名
    sys.argv[0] = "ordina-cli"
    main()
    return 0


if __name__ == "__main__":
    sys.exit(run())
