"""
Ordina GUI 打包入口（供 PyInstaller 使用）
=========================================

打包后双击即可启动图形界面；不需要任何参数。
与 ordina/__main__.py 的区别：__main__ 需要靠参数区分 GUI / CLI，
打包成 exe 后应各司其职，故 GUI 单独一个入口。
"""

import sys

from ordina.ui.app import launch


def run() -> int:
    return launch()


if __name__ == "__main__":
    sys.exit(run())
